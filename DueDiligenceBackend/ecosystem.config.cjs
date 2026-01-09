module.exports = {
  apps: [
    {
      name: 'flask-backend',
      script: 'python3',
      args: '"Due Diligence/app.py"',
      cwd: '/home/user/webapp/DueDiligenceBackend',
      env: {
        PYTHONUNBUFFERED: '1'
      },
      instances: 1,
      exec_mode: 'fork',
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: 'ai-sme',
      script: 'python3',
      args: '-m uvicorn app:app --host 0.0.0.0 --port 8000',
      cwd: '/home/user/webapp/DueDiligenceBackend/AI SME',
      env: {
        PYTHONUNBUFFERED: '1'
      },
      instances: 1,
      exec_mode: 'fork',
      watch: false,
      autorestart: true,
      max_restarts: 10
    }
  ]
}
