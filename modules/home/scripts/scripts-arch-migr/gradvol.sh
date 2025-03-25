#!/usr/bin/env bash

pulseaudio-control --volume-max 100 --volume-step 100 down
pulseaudio-control --volume-max 100 --volume-step 16 up

for i in $(seq 1 42); do
  pulseaudio-control --volume-max 100 --volume-step 2 up
  sleep 2
done
