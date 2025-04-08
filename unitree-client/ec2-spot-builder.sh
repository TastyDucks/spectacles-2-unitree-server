#!/usr/bin/env bash
set -euo pipefail

AMI_ID="ami-0e8c824f386e1de06"  # Ubuntu ARM64 in us-west-2
INSTANCE_TYPE="c8g.16xlarge"
KEY_NAME="1Password AWS"
SEC_GROUP="sg-03626937"
SUBNET_ID="subnet-3005b27a"
AVAIL_ZONE="us-west-2a"
REGION="us-west-2"
VOLUME_SIZE=100
SPOT_PRICE="0.50"

# Encode user-data
USERDATA=$(base64 -w0 <<'EOF'
#!/bin/bash
set -eux
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update && sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin
(type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
	&& sudo mkdir -p -m 755 /etc/apt/keyrings \
        && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
	&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
	&& sudo apt update \
	&& sudo apt install gh -y
curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
EOF
)

# Request spot instance (persistent)
SPOT_REQ=$(aws ec2 request-spot-instances \
  --region "$REGION" \
  --spot-price "$SPOT_PRICE" \
  --instance-count 1 \
  --type "persistent" \
  --launch-specification "{
    \"ImageId\": \"$AMI_ID\",
    \"InstanceType\": \"$INSTANCE_TYPE\",
    \"KeyName\": \"$KEY_NAME\",
    \"SecurityGroupIds\": [\"$SEC_GROUP\"],
    \"Placement\": {\"AvailabilityZone\": \"$AVAIL_ZONE\"},
    \"BlockDeviceMappings\": [{
      \"DeviceName\": \"/dev/sda1\",
      \"Ebs\": {
        \"VolumeSize\": $VOLUME_SIZE,
        \"VolumeType\": \"gp3\",
        \"DeleteOnTermination\": false
      }
    }],
    \"InstanceInterruptionBehavior\": \"stop\",
    \"UserData\": \"$USERDATA\"
  }")

SPOT_ID=$(echo "$SPOT_REQ" | jq -r '.SpotInstanceRequests[0].SpotInstanceRequestId')
echo "📥 Spot request ID: $SPOT_ID"

# Wait for fulfillment
echo "⏳ Waiting for spot request to fulfill..."
while true; do
  INSTANCE_ID=$(aws ec2 describe-spot-instance-requests \
    --region "$REGION" \
    --spot-instance-request-ids "$SPOT_ID" \
    --query 'SpotInstanceRequests[0].InstanceId' \
    --output text)

  if [[ "$INSTANCE_ID" != "None" ]]; then
    echo "✅ Instance ID: $INSTANCE_ID"
    break
  fi
  sleep 5
done

# Wait until instance is running
aws ec2 wait instance-running \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID"

echo "🚀 Instance is running! SSH: ec2-user@$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)"

# Auto-SSH (assumes agent-forwarded key)
IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "🔑 Connecting to $IP..."
ssh -o StrictHostKeyChecking=no ec2-user@"$IP"