{ inputs, ... }:
{
  perSystem =
    { system, pkgs, ... }:
    let
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      ports = import ../data/ports.nix;
      hostPkgs = inputs.self.nixosConfigurations.sinnix-prime.pkgs;
      files = ../../pkgs/llama-http-admission;
      native = hostPkgs.llama-cpp;
      cuda = hostPkgs.llama-cpp-cuda;
      profilePolicies = pkgs.lib.mapAttrsToList (
        name: profile:
        let
          pair = ports.${profile.portKey};
          expected =
            "SINNIX_LLAMA_ALLOWED_ORIGINS="
            + pkgs.lib.concatStringsSep "," (
              pkgs.lib.concatMap
                (
                  address:
                  map (port: "http://${address}:${toString port}") [
                    pair.public
                    pair.backend
                  ]
                )
                [
                  "127.0.0.1"
                  "localhost"
                  "[::1]"
                ]
            );
          actual =
            builtins.filter (pkgs.lib.hasPrefix "SINNIX_LLAMA_ALLOWED_ORIGINS=")
              host.systemd.services.${name}.serviceConfig.Environment;
        in
        actual == [ expected ]
      ) (pkgs.lib.filterAttrs (_: profile: profile.enable) host.sinnix.services.llama-cpp.profiles);
    in
    {
      checks.llama-http-admission =
        pkgs.runCommand "llama-http-admission-check"
          {
            nativeBuildInputs = [
              pkgs.stdenv.cc
              pkgs.python3
            ];
          }
          ''
            for source in ${native.src} ${cuda.src}; do
              c++ -std=c++17 -O0 -pthread -I${files} -I"$source/vendor" \
                ${files}/fixture.cpp "$source/vendor/cpp-httplib/httplib.cpp" -o fixture
              python3 ${files}/test_http.py "$PWD/fixture" --fixture
            done
            touch "$out"
          '';
      checks.llama-package-admission =
        pkgs.runCommand "llama-package-admission-check"
          {
            nativeBuildInputs = [ pkgs.python3 ];
          }
          ''
            python3 ${files}/test_http.py ${native}/bin/llama-server
            python3 ${files}/test_http.py ${cuda}/bin/llama-server
            touch "$out"
          '';
    };
}
