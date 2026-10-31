# 操作與驗證說明

PackScope 使用對應套件管理器執行安裝、更新和移除，系統權限操作透過 Ubuntu polkit / pkexec 授權。指令以參數陣列執行，不使用 shell 串接；密碼由系統授權代理處理。

APT、Snap、Flatpak、pipx、npm、Cargo 操作的命令建構和介面背景流程已以模擬呼叫進行自動測試。AppImage 複製及桌面捷徑已在暫存目錄中測試。原生 polkit 密碼視窗和各管理器的真實安裝／更新／移除流程尚未在隔離環境中端到端測試。

2026-10-31 曾以 Ubuntu 24.04 隔離虛擬機及測試套件驗證 APT 本身的安裝、升級、移除和依賴模擬；該測試不是 PackScope 圖形介面與授權流程的端到端驗證，腳本保存在 `tests/vm/user-data`。
