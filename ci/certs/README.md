# SAPS TLS CA bundle

`saps-chain.pem` holds two public CA certificates, in PEM, used as `curl --cacert` when downloading the official SAPS quarterly workbook.

The SAPS site presents only its leaf certificate (issued to www.saps.gov.za by Sectigo Public Server Authentication CA OV R36). A default CA store therefore fails with "unable to get local issuer certificate". The bundle supplies the missing intermediate and the root. It is not a reason to disable TLS verification.

| Certificate | Source | SHA256 fingerprint |
|---|---|---|
| Sectigo Public Server Authentication CA OV R36 | The leaf's AIA caIssuers URI, `http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt` | `65:42:D1:76:BE:D5:0F:19:3C:0C:E2:97:AE:44:EC:D8:A0:A8:6B:EC:2E:DE:68:27:69:34:40:59:B4:E7:85:30` |
| Sectigo Public Server Authentication Root R46 | Official Sectigo root download, `http://crt.sectigo.com/SectigoPublicServerAuthenticationRootR46.crt` | `7B:B6:47:A6:2A:EE:AC:88:BF:25:7A:A5:22:D0:1F:FE:A3:95:E0:AB:45:C7:3F:93:F6:56:54:EC:38:F2:5A:06` |

The leaf itself is not stored in this repository.
