# Weedhack Stealer Remover

Simple tool to remove the Weedhack stealer malware, primarily targeting Minecraft players.

```
detection_rules:
  strings:
    high_confidence:
      - "me/mclauncher/LoaderClient"
      - "me/mclauncher/StagingHelper"
      - "me/mclauncher/RPCHelper"
      - "me/mclauncher/MEntrypoint"
      - "dev/majanito/Main"
      - "dev/majanito/handlers"
      - "dev/majanito/security"
      - "initializeWeedhack"
      - "WeedhackFile"
      - "WeedhackLog"
      - "dev/jnic/BSOMwJ"
      - "dev/jnic/fwcMeR"
      - "dev/jnic/lXpXvp"
      - "$jnicLoader"
      - "a125e430-2459-4702-9797-49fce5f280ae"
      - "c4f763d6-e34c-42e9-bba1-b80cfa5a55df"
      - "JavaSecurityUpdater"
      - "SecurityUpdates"
      - "KeyLoggingHandler"
      - "WebcamShareHandler"
      - "ScreenShareHandler"
      - "0xce6d41de"
    medium_confidence:
      - "Mod init state: M"
      - "Resource state: S"
      - "receiver.cy"
      - "Add-MpPreference -ExclusionPath"
      - "schtasks /Create"
      - "component-"
    low_confidence:
      - "me/mclauncher/IMCL"
      - "cfg.json"
      - "SecurityInfo.json"
      - "Updater.vbs"

  file_patterns:
    - pattern: "PK\\x03\\x04"
      offset: 0
      description: "ZIP/JAR magic"
    - pattern: "META-INF/MANIFEST.MF"
      description: "JAR manifest"

  network_iocs:
    domains:
      - "receiver.cy"
      - "weedhack.cy"
    urls:
      - "https://receiver.cy/files/jar/module"
      - "https://receiver.cy/files/jar/component"
      - "https://receiver.cy/api/component/lastModified"
    websocket_endpoints:
      - "screen share via WebSocket (WebP encoded)"
      - "webcam stream via WebSocket (25 FPS)"
    socket_io:
      - "keylogger data via Socket.IO"
    blockchain_c2:
      ethereum_function_selector: "0xce6d41de"
      rsa_public_key: "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtmNzDf4737/iYWvscWg6vQg9dHa/yUchfQY9r5htNTLZ3ZDAbqrzN93I0ctZHa27oRnkpB7XpowI4NH8eIRmaMThggpTYRXzHzLvUjhyrFFPkIOo/HI1gZF5IV7/XmvYWqgEsSpxl0iesOUlaWO5A8QlTu0QLsZAzZtzZyLj/v1XbPT02rTvZkuRhE6nzpUR4GN3Jp4Bn8zQAWdFDe17PWZxOi19uUTMPzgFj9n3h7DprwBmE3fR7IMsbiFacAoSHfqkTpEwY7A8ArK1DQ1yJXPog/PQ4aTU9gU38WC20wtct796ImZiuRYdNWcSzHda5ZbvZdvpw6RHh0zQqGVhRQIDAQAB"
      description: "v2 Stage1 uses Ethereum RPC calls to retrieve RSA-signed C2 config from blockchain as fallback"

  file_iocs:
    paths:
      - "%TEMP%\\lib*.tmp"
      - "%APPDATA%\\Microsoft\\SecurityUpdates"
      - "%APPDATA%\\Microsoft\\SecurityUpdates\\SecurityInfo.json"
      - "%APPDATA%\\Microsoft\\SecurityUpdates\\Updater.vbs"
      - "%APPDATA%\\Microsoft\\SecurityUpdates\\component-*.jar"
      - "%APPDATA%\\Microsoft\\SecurityUpdates\\security.lock"
    resources:
      - "/dev/jnic/lib/a125e430-2459-4702-9797-49fce5f280ae.dat"
      - "/dev/jnic/lib/c4f763d6-e34c-42e9-bba1-b80cfa5a55df.dat"
    scheduled_tasks:
      - "JavaSecurityUpdater"
    registry_keys:
      - "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"

  behavioral_iocs:
    persistence:
      - "schtasks /Create /TN \"JavaSecurityUpdater\" /SC ONLOGON /RL HIGHEST"
      - "VBScript launcher in hidden window"
    av_evasion:
      - "Add-MpPreference -ExclusionPath 'C:\\Users'"
    privilege_escalation:
      - "ShellExecute with 'runas' verb for UAC bypass"

obfuscation:
  type: "JNIC + Custom String Encryption"
  string_encryption:
    algorithm: "interleave-xor-rotate-substitute"
    keys: [187, 67]
    decodable: true
  jnic_variants:
    - "dev.jnic.BSOMwJ (Module.jar - Stage2)"
    - "dev.jnic.fwcMeR (Component.jar - Stage3 RAT)"
    - "dev.jnic.lXpXvp (NewMod.jar - Stage1 v2)"
```

