{ mkServiceTest, hmFor, ... }:
mkServiceTest {
  name = "services-terminal-capture";
  service = "terminal-capture";
  assertions = config: [
    {
      assertion = (hmFor config).home.file ? ".local/bin/sinnix-captured-shell";
      message = "The terminal capture launcher must be linked into ~/.local/bin";
    }
  ];
}
