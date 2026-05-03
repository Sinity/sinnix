let
  developerWork = rec {
    cpuWeight = 20;
    ioWeight = 50;

    sliceConfig = {
      CPUWeight = cpuWeight;
      IOWeight = ioWeight;
    };
  };

  graphical = {
    sliceConfig = {
      CPUWeight = 800;
      IOWeight = 800;
    };
  };
in
{
  inherit developerWork graphical;
}
