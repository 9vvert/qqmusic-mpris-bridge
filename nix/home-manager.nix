{
  config,
  lib,
  pkgs,
  ...
}: let
  cfg = config.services.qqmusic-mpris-bridge;
  inherit
    (lib)
    concatStringsSep
    escapeShellArgs
    getExe
    literalExpression
    mapAttrsToList
    mkEnableOption
    mkIf
    mkOption
    types
    ;

  commandArgs =
    [
      "--fallback-interval"
      (toString cfg.fallbackInterval)
      "--debounce-ms"
      (toString cfg.debounceMs)
      "--art-sources"
      (concatStringsSep "," cfg.artSources)
      "--max-art-cache-items"
      (toString cfg.maxArtCacheItems)
    ]
    ++ lib.optional cfg.debug "--debug"
    ++ lib.optional (!cfg.noctaliaPreference) "--no-noctalia-preference"
    ++ cfg.extraArgs;
in {
  options.services.qqmusic-mpris-bridge = {
    enable = mkEnableOption "QQMusic MPRIS artwork bridge user service";

    package = mkOption {
      type = types.package;
      default = pkgs.callPackage ./package.nix {};
      defaultText = literalExpression "pkgs.callPackage ./nix/package.nix { }";
      description = "Package providing the qqmusic-mpris-bridge command.";
    };

    artSources = mkOption {
      type = types.listOf (types.enum [
        "qqmusic"
        "itunes"
      ]);
      default = ["qqmusic"];
      description = "Artwork sources passed to --art-sources. QQMusic is authoritative when present.";
    };

    fallbackInterval = mkOption {
      type = types.number;
      default = 30;
      description = "Low-frequency fallback scan interval, in seconds.";
    };

    debounceMs = mkOption {
      type = types.number;
      default = 350;
      description = "Delay before refreshing after MPRIS events, in milliseconds.";
    };

    maxArtCacheItems = mkOption {
      type = types.ints.positive;
      default = 10;
      description = "Maximum number of local artwork files kept in the LRU cache.";
    };

    noctaliaPreference = mkOption {
      type = types.bool;
      default = true;
      description = "Ask Noctalia to prefer the bridge player when a QQMusic track is available.";
    };

    debug = mkOption {
      type = types.bool;
      default = false;
      description = "Enable debug logging.";
    };

    environment = mkOption {
      type = types.attrsOf types.str;
      default = {};
      example = {
        QQMUSIC_MPRIS_BRIDGE_ART_SOURCES = "qqmusic";
      };
      description = "Additional environment variables for the systemd user service.";
    };

    extraArgs = mkOption {
      type = types.listOf types.str;
      default = [];
      example = [
        "--no-noctalia-preference"
      ];
      description = "Extra command-line arguments appended to qqmusic-mpris-bridge.";
    };
  };

  config = mkIf cfg.enable {
    home.packages = [cfg.package];

    systemd.user.services.qqmusic-mpris-bridge = {
      Unit = {
        Description = "QQMusic MPRIS artwork bridge";
        After = ["graphical-session.target"];
        PartOf = ["graphical-session.target"];
      };

      Service = {
        Type = "simple";
        ExecStart = "${getExe cfg.package} ${escapeShellArgs commandArgs}";
        Restart = "on-failure";
        RestartSec = 5;
        Environment =
          ["PYTHONUNBUFFERED=1"]
          ++ mapAttrsToList (name: value: "${name}=${value}") cfg.environment;
      };

      Install = {
        WantedBy = ["default.target"];
      };
    };
  };
}
