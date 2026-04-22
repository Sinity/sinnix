let
  developerWork = rec {
    memoryHigh = "22G";
    memoryMax = "26G";
    memorySwapMax = "0";
    cpuQuota = "2200%";
    cpuWeight = 20;
    ioWeight = 50;
    managedOOMMemoryPressure = "kill";
    managedOOMMemoryPressureLimit = "50%";

    sliceConfig = {
      MemoryHigh = memoryHigh;
      MemoryMax = memoryMax;
      MemorySwapMax = memorySwapMax;
      ManagedOOMMemoryPressure = managedOOMMemoryPressure;
      ManagedOOMMemoryPressureLimit = managedOOMMemoryPressureLimit;
      CPUQuota = cpuQuota;
      CPUWeight = cpuWeight;
      IOWeight = ioWeight;
    };
  };

  graphical = {
    sliceConfig = {
      MemoryHigh = "18G";
      MemoryMax = "24G";
      MemorySwapMax = "1G";
      ManagedOOMMemoryPressure = "kill";
      ManagedOOMMemoryPressureLimit = "60%";
      CPUWeight = 800;
      IOWeight = 800;
    };
  };
in
{
  inherit developerWork graphical;
}
