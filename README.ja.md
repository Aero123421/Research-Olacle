# Codex Research Harness

**人間の曖昧な要望を、Codex Goal Modeによる観測可能な自律研究ループへ変えるWindows対応テンプレートです。**

中心は次の二層です。

```text
Research Planner
広い調査、ルール、EDA、データ生成過程、他分野、戦略を担当
        ↓
明確なCampaign Contract
        ↓
GPT-5.6 Sol High /goal Research Executor
1つの目標を数時間〜1日、深く自律追求
        ↓
証拠付きHandoff
        ↓
Research Plannerが次を再計画
```

この遷移は会話の記憶ではなく、ResearchPlan、Campaign Contract、STATE、
Handoffから`researchctl loop`が機械的に判定します。

人間は研究判断の承認者ではありません。Codex Appとの会話では、研究所が正常か、今何をしているか、勝ち筋が強くなったか、時間・GPU・費用、次に何が起こるかを確認します。

## 開始方法

```powershell
git clone https://github.com/Aero123421/Research-Olacle.git my-research
cd my-research
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\bootstrap.ps1 -Initialize
```

この初期化では、Git管理外のローカル診断・面談状態だけを保存するため、
clone直後の作業ツリーは汚れません。設定ファイルを生成する前に、個別の
private研究リポジトリへ切り替えます。

```powershell
researchctl repo adopt OWNER/NEW-RESEARCH-REPO --visibility private
```

そのフォルダをWindowsのCodexで開き、曖昧な要望と対象URLを伝えてください。詳しい初期化契約は[BOOTSTRAP.md](BOOTSTRAP.md)、非エンジニア向け案内は[`docs/ja/はじめに.md`](docs/ja/はじめに.md)にあります。

## 初期化で行うこと

- Git、GitHub CLI、Codex、Claude Code、Grok Build、agmsg、Kaggle CLIを実動作確認
- CPU、RAM、ディスク、GPU、追加計算環境と予算を確認
- Codex内蔵ブラウザかChromeを選択
- ChatGPTへログインし、研究専用Projectを1つ作成
- 実際のモデルセレクターからProを選び、選択状態を検証
- GitHub Project、フィールド、Issue、研究ビューを構築
- 人間向け説明レベルを記録
- Doctor、テスト、復旧確認
- ResearchPlan PRを作成し、自律研究へ移行

## Plannerの役割

Plannerは単なる文章作成AIではありません。Kaggleなら、ルール、評価指標、提出方式、データ構造、train/test差、リーク候補、EDA、ベースライン、CV、計算時間を把握します。さらに中心ドメイン、隣接分野、古典手法、否定的結果、過去コンペ、論文、Discussion、X上の最新動向を広く調査し、ChatGPT Pro、Claude、Grokへ独立相談した上で目標と撤退ラインを決めます。

## ChatGPT Pro

ChatGPT Proは狭い役割に固定しません。PlannerとExecutorの両方が、問題設定、データ解釈、ドメイン知識、他分野の類推、実験設計、異常、実装、戦略の再定義まで幅広く相談できます。

新しい問いは研究Project内の新規チャット、同じ問いの深掘りは保存済み会話URLへの追質問として管理します。モデルは表示名を厳密に確認し、勝手なフォールバックを禁止します。

## GitHub

- GitHub Project: 人間向け研究管制盤
- Issue: Mission、Strategy、Campaign、例外
- Pull Request: 計画、コード、実験証拠、結論
- リポジトリ: 研究状態の正本
- agmsg: 生きているエージェントへの通知路。研究状態の正本ではない

## ライセンス

Apache License 2.0。

## 主なコマンド

```powershell
# 初期化と診断
researchctl init --answers .research-lab\local\init-answers.json
researchctl doctor --profile quick
researchctl repo adopt OWNER/NEW-RESEARCH-REPO --visibility private
researchctl doctor --profile full
researchctl github setup

# 曖昧な要望をResearchPlanへ保存
researchctl plan create --intent-file mission.txt --target "https://..."
researchctl context planner

# Plannerが作ったContractを検証し、/goal研究を開始
researchctl campaign validate C-001
researchctl campaign finalize C-001
researchctl campaign activate C-001
researchctl context executor C-001
researchctl campaign claim-executor C-001 --session-id <GOAL_SESSION_ID> --worktree <WORKTREE>
researchctl loop checkpoint
researchctl loop instruction

# 時間・GPU・実験・人間向け表示
researchctl job register --campaign C-001 --name "quick validation" --resource GPU0 --planned-hours 1
researchctl brief
researchctl visualize
```

## 1つのリポジトリから新しい研究を始める

clone直後のリポジトリをprivateな個別研究リポジトリへ変換できます。

```powershell
researchctl repo adopt OWNER/NEW-RESEARCH-REPO --visibility private
```

元の`origin`は`template-upstream`へ移され、新しい研究リポジトリが`origin`になります。コマンドは未commitの変更がある場合、安全のため停止します。adopt成功後にだけ、人間プロフィールや計算・自律方針などのレビュー可能な設定ファイルを生成します。

## ChatGPT Projectのブラウザ選択

初期化時に、次のどちらかを選びます。

- Codex内蔵Browser
- ChatGPT/CodexのPluginsから導入する公式Codex Chrome拡張

どちらでも、研究専用ChatGPT Projectを1つだけ作り、作成時にproject-only memoryを選びます。重要な質問の前にはモデル表示が完全一致で`Pro`になっていることを確認し、別モデルへ黙って切り替えません。Project URLと会話URLはGit管理外のローカル状態だけに保存します。

## 開発・検証

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\researchctl.exe self-test
.\scripts\verify.ps1
```

詳しい設計は[`docs/architecture.md`](docs/architecture.md)、初回面談は[`docs/INITIAL_INTERVIEW.md`](docs/INITIAL_INTERVIEW.md)、参照した公式仕様は[`docs/UPSTREAM_REFERENCES.md`](docs/UPSTREAM_REFERENCES.md)にあります。
