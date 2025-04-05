sudo docker run -it --rm \
  --runtime nvidia \
  --network host \
  --device /dev/eth0 \
  --privileged \
  docker pull ghcr.io/tastyducks/spectacles-2-unitree-server.client:latest