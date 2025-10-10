# Host-specific audio configuration for sinnix-prime
# Only hardware-specific configuration remains here
# Generic audio configuration is in the media domain module

_: {
  # Hardware-specific audio configuration
  # This stays in the host module as it's specific to the hardware

  # Example: If you have specific audio hardware that needs configuration
  # boot.extraModprobeConfig = ''
  #   options snd-hda-intel model=dell-headset-multi
  # '';

  # Note: Generic PipeWire configuration has been moved to media domain
  # Note: Audio group membership is handled by media domain
  # Note: System packages are provided by media domain
}
