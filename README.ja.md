# Codex Research Harness

**人間の曖昧な要望を、Codex Goal Modeによる観測可能な自律研究ループへ変えるWindows対応テンプレートです。**

中心は次の二層です。

```text
Research Planner
広い調査、ルール、EDA、データ生成過程、他分野、戦略を担当
        ↓
明確なCampaign Contract
        ↓
設定済みResearch Executor runtime profile
1つの目標を数時間〜1日、深く自律追求
        ↓
証拠にアンカーされたHandoff
        ↓
Research Plannerが次を再計画
```

この遷移は会話の記憶ではなく、ResearchPlan、Campaign Contract、STATE、
Handoffから`researchctl loop`が機械的に判定します。

CampaignとResearchPlanはrevision付きの明示状態機械です。実行中の変更とJob操作は
現在のExecutor claimへ束縛され、古いExecutorはfencing generationで拒否されます。
科学的な主張は運用状態とは別に、証拠・前提・確信度・反証条件・失効・更新履歴を
持つappend-onlyの`CLAIMS.jsonl`へ記録します。

`researchctl loop`自体はAIプロセスを起動しません。永続状態から次の指示を決定し、
Codex App Director、スケジュール済みタスク、またはprovider adapterが実行します。
adapterにlaunch/status/cancelの実装がなければ、外部計算の停止は協調的な要求です。

人間は実験ごとの逐次承認者ではありません。ただし、Mission、価値判断、データ・法的境界、ハード予算、外部公開の最終責任を持ちます。Codex Appとの会話では、研究所が正常か、今何をしているか、勝ち筋が強くなったか、時間・GPU・費用、次に何が起こるかを確認します。

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
$claim = researchctl campaign claim-executor C-001 --session-id <GOAL_SESSION_ID> --worktree <WORKTREE> | ConvertFrom-Json
$claimId = $claim.executor.claim_id
researchctl loop checkpoint
researchctl loop instruction

# revision付きcheckpoint、claimへ束縛したJob、認識上の主張
researchctl campaign checkpoint C-001 --claim-id $claimId --expected-revision <REVISION> --patch checkpoint.json
researchctl job register --campaign C-001 --name "quick validation" --resource GPU0 --planned-hours 1 --claim-id $claimId
researchctl job start <JOB_ID> --claim-id $claimId
researchctl claim-ledger record --statement "..." --confidence 0.4 --falsifier "..."
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

## 安全性と成熟度

外部計算の停止要求と実停止は別状態です。実行中Jobを`cancelled`にするには、
停止確認と監査可能なPID・scheduler ID等の参照が必要です。有料計算は、停止と
provider側料金計測を実装したコード登録済みadapterがない限りfail closedします。
各backendは有料か無料かを明示し、有料backendでは正のJob費用見積もりを必須に
するため、`planned_cost_jpy = 0`では安全検査を迂回できません。
現時点のプロジェクト成熟度は**Alpha**です。

## 開発・検証

```powershell
.\scripts\bootstrap.ps1
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\researchctl.exe self-test
.\scripts\verify.ps1
```

詳しい設計は[`docs/architecture.md`](docs/architecture.md)、初回面談は[`docs/INITIAL_INTERVIEW.md`](docs/INITIAL_INTERVIEW.md)、参照した公式仕様は[`docs/UPSTREAM_REFERENCES.md`](docs/UPSTREAM_REFERENCES.md)にあります。
