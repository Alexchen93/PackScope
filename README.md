# PackScope 0.2.0 開發版

PackScope 是基於 [bauh](https://github.com/vinifmor/bauh) 修改的 Ubuntu 軟體管理介面。此專案保留 bauh 原始程式與授權，並提供新的繁體中文介面。

可查看、搜尋及管理 APT、Snap、Flatpak、AppImage 與部分開發工具；支援本機安裝檔、個別與批次更新、移除，以及作業輸出。

## 啟動與使用

在 Ubuntu 安裝 Python 3、PyQt5 與本專案所需的 bauh 相依套件後，於專案目錄執行：

```bash
./packscope.sh
```

各來源需要相應的系統套件管理器。完整操作方式、支援範圍與限制請參考 [PackScope 使用說明](packscope/README.md)及[操作與驗證說明](packscope/SAFETY.md)。

在 Ubuntu 上可執行 `sh packaging/build-deb.sh` 建立 DEB 安裝檔，輸出至 `dist/`；安裝後可從應用程式選單啟動。

## 上游與授權

此專案修改自 [bauh](https://github.com/vinifmor/bauh)，保留其 [zlib/libpng 授權](LICENSE)。上游原始說明可見 [README.bauh.md](README.bauh.md)。
