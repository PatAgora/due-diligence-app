module.exports = {
  apps: [
    {
      name: 'ai-sme',
      script: 'uvicorn',
      args: 'app:app --host 0.0.0.0 --port 8000',
      cwd: '/home/user/webapp/DueDiligenceBackend/AI SME',
      interpreter: 'none', // Use system uvicorn
      env: {
        NODE_ENV: 'production',
        PORT: 8000
      },
      watch: false,
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s'
    }
  ]
}
