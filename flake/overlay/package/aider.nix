_:
final: prev: {
  aider-chat-full = prev.aider-chat-full.override {
    pythonPackages = final.python3Packages;
  };
}
