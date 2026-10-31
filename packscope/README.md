# PackScope 0.1.0

PackScope 是以 bauh 為基底的 Ubuntu 軟體管理介面，使用 PyQt5。

## 啟動

```bash
cd PackScope
./packscope.sh
```

## 使用

- 按「安裝軟體」選擇本機 `.deb`、`.snap`、`.flatpak`、`.flatpakref` 或 `.AppImage` 檔案，程式會依副檔名選擇套件管理器，安裝完成後重新掃描清單。Flatpak 檔案安裝至目前使用者；AppImage 會複製到 `~/Applications` 並建立桌面捷徑。本機 Snap 使用 `--dangerous`，不驗證商店簽章；某些 Snap 可能另有安裝限制。
- 按「安裝軟體」右側的箭頭，選「依名稱安裝」可使用原有的來源安裝方式：APT 可搜尋套件，Snap、Flatpak、pipx、npm 和 Cargo 可輸入名稱或 ID。
- 從清單選擇項目，按「開啟」、「更新」或「移除」。只有辨識到可用啟動方式的應用程式才能開啟。AppImage 移除會將檔案及 PackScope 建立的捷徑移至垃圾桶；AppImage 不提供統一的更新操作。
- 需要管理員權限時，Ubuntu 會開啟系統授權視窗供輸入密碼。PackScope 不接收或保存密碼。
- 視窗下方固定顯示輸出紀錄；開啟程式時是空白的，之後保留本次執行期間的操作與輸出。操作在背景執行，進度列顯示實際指令及即時輸出，完成後重新整理清單。能取得百分比時顯示該階段的進度；管理器未提供百分比時顯示執行中動畫。
- 可以搜尋、篩選、排序、查看詳細資料，查詢更新、查看 APT 變更紀錄，以及匯出 JSON、CSV、Markdown。上方工具列的問號統一說明各個軟體來源。

## 範圍與依賴

需要 Python 3、PyQt5、bauh 的 Python 相依套件，以及所使用來源的系統工具。部分系統工具可能未安裝。系統權限操作需要 `pkexec` 和可用的圖形化 polkit 授權代理。

APT 清單包含系統程式庫；Flatpak 也包含執行環境。AppImage 僅掃描 `~/Applications`、`~/AppImages`、`~/Downloads` 第一層和 bauh 安裝紀錄。開發工具只涵蓋目前使用者的 pipx、目前 PATH 中 npm 的全域環境與目前 CARGO_HOME。

APT 更新查詢使用本機套件清單，Flatpak 使用本機快取，Snap 會連線查詢。AppImage 與開發工具的統一更新查詢尚未提供；個別開發工具的更新按鈕會呼叫其管理器。

## 上游

基於 [bauh](https://github.com/vinifmor/bauh)，上游提交 `b1ea479a3aed504e0ddc329f2474e9a93331927c`。原始程式碼與授權保留在專案根目錄。
