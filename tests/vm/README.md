# 隔離 APT 基本行為測試

`user-data` 是 NoCloud cloud-init 設定：在 Ubuntu 24.04 VM 內建立無害 `.deb` 測試套件，檢查 APT 模擬與實際安裝、升級和移除。測試成功時在 VM 的序列埠印出 `PACKSCOPE_VM_SUCCESS`，然後關閉 VM。

2026-10-31 使用 Ubuntu minimal cloud image SHA-256 `3839f148c5a3b4a736e7dbb0af75594743fa5ebee2a202424ba1a32e5d3b5d2c`，QEMU `-snapshot` 和 `-nic user,restrict=on` 進行；未對外連線，也未在主機進行套件變更。這不是 PackScope 圖形介面或 polkit 授權的端到端測試。
