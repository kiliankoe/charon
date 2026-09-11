{
  description = "charon, transitional keyboard layouts for moving from NeoQwertz to Bone";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            python3
            ruff
          ];
        };
      });

      packages = forAllSystems (pkgs: {
        # The generator as a command, for building a bundle from other inputs
        # (a locally patched Bone, a different path file).
        charon = pkgs.stdenvNoCC.mkDerivation {
          pname = "charon";
          version = "0.1.0";
          src = self;
          buildInputs = [ pkgs.python3 ];
          installPhase = ''
            mkdir -p $out/bin $out/share/charon
            cp charon.py $out/bin/charon
            chmod +x $out/bin/charon
            cp -r paths upstream $out/share/charon/
          '';
        };

        # The bundle built from the official layouts: Charon 0 to 4.
        default = pkgs.stdenvNoCC.mkDerivation {
          pname = "charon-bundle";
          version = "0.1.0";
          src = self;
          nativeBuildInputs = [ pkgs.python3 ];
          buildPhase = ''
            python3 charon.py build --target "upstream/Deutsch (Bone).keylayout" \
              --out Charon.bundle paths/stage0.txt paths/charon.txt
          '';
          installPhase = ''
            mkdir -p $out
            cp -r Charon.bundle $out/
          '';
        };
      });

      checks = forAllSystems (pkgs: {
        tests = pkgs.runCommand "charon-tests" { nativeBuildInputs = [ pkgs.python3 ]; } ''
          cd ${self}
          python3 -m unittest discover -s tests -v
          touch $out
        '';
      });
    };
}
