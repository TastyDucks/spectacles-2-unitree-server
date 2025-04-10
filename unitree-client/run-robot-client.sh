sudo docker run \
  -p 7000:7000 \
  -it \
  --rm \
  --runtime=nvidia \
  --gpus=all \
  --net=host \
  --cap-add=NET_ADMIN \
  ghcr.io/tastyducks/spectacles-2-unitree-server.client:latest