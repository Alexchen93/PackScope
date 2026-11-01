# 發行前檢查清單

此清單不會自動發布或修改既有 GitHub release。依序記錄 commit、版本與產物；若其中一項失敗，先停止發行。

- [ ] 確認工作目錄乾淨，記錄待發行 commit；檢查 `packscope/__init__.py` 的版本與 README／CHANGELOG 使用相同版本及功能描述。
- [ ] 執行 CI 對應的離線 Qt 測試：`QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p 'test_packscope*.py'`。
- [ ] 執行 `python3 -m compileall -q packscope` 與 `python3 -m pycodestyle --select=E9,W191,W291,W293 packscope`；確認 CI 通過。
- [ ] 執行 `sh packaging/build-deb.sh`，用 `dpkg-deb -f <DEB> Version` 核對版本；核對桌面入口、依賴與執行檔。
- [ ] 在可還原的 Ubuntu 24.04 Desktop VM 安裝此 DEB，依 [`desktop-checklist.md`](desktop-checklist.md) 驗證 GUI 與原生 polkit。不要把 offscreen 測試當成此項結果。
- [ ] 記錄 DEB 檔案的 SHA-256、commit、測試結果與已知限制，確認下載文件指向實際上傳的檔名與版本。
- [ ] 經人工確認後才建立 tag／GitHub release、上傳 DEB 並更新文件；若已有 release 指向舊產物，明確註記，不要假設它包含目前主線功能。
