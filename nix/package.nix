{
  lib,
  python3Packages,
}:
python3Packages.buildPythonApplication {
  pname = "qqmusic-mpris-bridge";
  version = "0.1.0";
  src = lib.cleanSource ../.;

  pyproject = true;

  build-system = with python3Packages; [
    setuptools
    wheel
  ];

  dependencies = with python3Packages; [
    dbus-next
    requests
  ];

  pythonImportsCheck = ["qqmusic_mpris_bridge"];

  postInstall = ''
    install -Dm644 systemd/qqmusic-mpris-bridge.service.in \
      $out/lib/systemd/user/qqmusic-mpris-bridge.service
    substituteInPlace $out/lib/systemd/user/qqmusic-mpris-bridge.service \
      --replace-fail @EXECUTABLE@ $out/bin/qqmusic-mpris-bridge
  '';

  meta = {
    description = "Publish QQMusic MPRIS metadata with resolved album artwork";
    mainProgram = "qqmusic-mpris-bridge";
    platforms = lib.platforms.linux;
  };
}
