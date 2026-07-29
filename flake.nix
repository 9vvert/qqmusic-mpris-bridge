{
  description = "QQMusic MPRIS artwork bridge";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    forAllSystems = nixpkgs.lib.genAttrs systems;
  in {
    packages = forAllSystems (
      system: let
        pkgs = import nixpkgs {inherit system;};
      in {
        default = pkgs.callPackage ./nix/package.nix {};
        qqmusic-mpris-bridge = self.packages.${system}.default;
      }
    );

    apps = forAllSystems (system: {
      default = {
        type = "app";
        program = "${self.packages.${system}.default}/bin/qqmusic-mpris-bridge";
        meta.description = "Run qqmusic-mpris-bridge";
      };
    });

    homeModules.default = import ./nix/home-manager.nix;
    homeModules.qqmusic-mpris-bridge = self.homeModules.default;
  };
}
