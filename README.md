<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/packscope-logo-dark.svg">
    <img src="assets/packscope-logo-light.svg" alt="PackScope" width="430">
  </picture>
</p>

<p align="center"><strong>讓 Ubuntu 上的軟體與套件，一目了然。</strong></p>

PackScope 將不同來源的軟體整理到同一個介面。從搜尋、查看資訊，到安裝、更新及移除，都能在同一個視窗中完成，同時保留各來源原本的管理方式。

<p align="center">
  <img src="assets/packscope-preview.png" alt="PackScope 軟體管理介面，顯示來源篩選、套件清單與詳細資料" width="900">
  <br><sub>介面預覽，使用示意資料。</sub>
</p>

## 軟體管理，一個視窗就夠

- **集中查看不同來源**：瀏覽 APT / dpkg、Snap、Flatpak、AppImage，以及 pipx、npm global 和 Cargo 的已偵測項目；可依來源篩選和搜尋名稱、套件 ID 或描述。
- **更快找到應用程式**：切換「僅顯示應用程式」，依桌面啟動項目與來源資料篩選；可辨識時顯示程式名稱與圖示。篩選可能因來源資料不完整而有遺漏。
- **直接安裝本機檔案**：選擇 `.deb`、`.snap`、`.flatpak`、`.flatpakref` 或 `.AppImage`，程式會依副檔名選擇對應的安裝方式；也可從按鈕選單依套件名稱安裝。
- **按需更新**：檢查 APT、Flatpak 與 Snap 的更新，選擇單一或多個已辨識項目執行；也能重新取得 APT 和 Flatpak 的來源資訊。
- **作業狀態看得見**：在下方輸出區查看指令與即時結果；管理器提供進度時顯示進度，否則顯示執行中狀態。輸出保留於目前執行期間。
- **依你的習慣調整**：支援深色、淺色及自訂配色；可調整清單欄寬、詳細資料面板與輸出區的大小。主題設定會保留到下次啟動。

## 安裝與啟動

目前提供 **0.2.0 開發版** DEB 安裝檔，適用 Ubuntu 24.04；其他環境尚未完整驗證。使用各種來源時，也需要對應的系統套件管理器。

### 下載安裝檔

1. [下載 PackScope DEB 安裝檔](https://github.com/Alexchen93/PackScope/releases/download/v0.2.0-dev.1/packscope_0.2.0.dev1_all.deb)。
2. 在檔案管理員中用軟體安裝程式開啟下載的 `.deb`，依畫面提示安裝。若系統沒有提供此選項，可在下載資料夾開啟終端機執行：

   ```bash
   sudo apt install ./packscope_0.2.0.dev1_all.deb
   ```

3. 安裝後，從應用程式選單開啟 **PackScope**，或在終端機執行 `packscope`。安裝時套件管理器會處理所需的系統依賴。

### 從原始碼建置

需要 Python 3.11 以上及 `dpkg-deb`。在 Ubuntu 上執行：

```bash
git clone https://github.com/Alexchen93/PackScope.git
cd PackScope
sh packaging/build-deb.sh
sudo apt install ./dist/packscope_0.2.0~dev1_all.deb
```

若只想從原始碼執行，請先安裝 Python、PyQt5、python3-gi 與專案相依套件，再執行 `./packscope.sh`。

## 使用提示

- 「安裝軟體」按鈕可選擇本機安裝檔；按按鈕右側箭頭可依名稱安裝。
- 按「檢查更新」後可勾選項目更新。APT 與 Flatpak 平常使用本機資料，Snap 會連線查詢；AppImage 與開發工具尚未納入統一更新查詢。
- AppImage 會區分 PackScope 管理的項目與偵測到的檔案；目前掃描 `~/Applications`、`~/AppImages`、`~/Downloads` 第一層，以及現有管理紀錄。
- 需要系統權限時，會由桌面環境顯示授權視窗。清單中的來源表示目前的管理方式。

更多操作細節、支援範圍與測試狀態請參考 [使用說明](packscope/README.md)及[操作與驗證說明](packscope/SAFETY.md)。

## 測試

在已安裝 PyQt5 等相依套件的環境中執行：

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_packscope*.py'
```

## 授權

請見 [LICENSE](LICENSE)。
