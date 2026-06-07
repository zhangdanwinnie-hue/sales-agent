$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "src"
$py = "C:\Users\wangj\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$zip = "C:\Users\wangj\Desktop\ZD 工作\ads_rpt_sal_ncs_register_to_order_sales_ssa_t_202605151845.zip"
$outDir = "outputs\real_data_demo"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
& $py -m bp_ba_agent.real_data $zip `
  --question "基于真实 register-to-order 数据演示媒体投流到订单转化分析" `
  --json-out "$outDir\real_data_demo_report.json" `
  --md-out "$outDir\real_data_demo_report.md" `
  --html-out "$outDir\real_data_demo_dashboard.html"
