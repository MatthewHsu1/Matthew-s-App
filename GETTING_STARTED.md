# 🚀 Quick Start Guide - Financial App

## What You Now Have

✅ **Go Backend** - REST API with PostgreSQL  
✅ **Next.js Frontend** - Modern web app with TypeScript  

## 🎯 Setup Instructions

### Step 1: Start the Backend
```bash
# In project root
docker-compose up -d
```
This starts PostgreSQL + Go API on `http://localhost:8080`

### Step 2: Install Node.js
- Download from: https://nodejs.org/ (version 18+)
- Verify: `node --version`

### Step 3: Start the Frontend
```bash
# In project root
cd frontend-nextjs
npm install
npm run dev
```
Open: `http://localhost:3000`

## ✨ What You'll See

🏠 **Dashboard** - Portfolio overview, top stocks, backend status  
📊 **Stocks Page** - Browse, search, and sort stocks  
📈 **Portfolio** - Coming soon placeholder  
👀 **Watchlist** - Coming soon placeholder  

## 🔧 Development Workflow

1. **Backend changes**: Restart `docker-compose up -d`
2. **Frontend changes**: Auto-reload with `npm run dev`
3. **Add features**: Edit files in `frontend-nextjs/src/`

## 🎨 Key Features

- **TypeScript**: Full type safety
- **Tailwind CSS**: Modern styling
- **Responsive**: Works on all devices
- **Mock Data**: Works even if backend is down
- **Real-time**: Connects to your Go API

## 📁 Important Files

```
frontend-nextjs/
├── src/app/page.tsx           # Dashboard
├── src/app/stocks/page.tsx    # Stock list
├── src/components/StockCard.tsx # Stock component
├── src/lib/api.ts             # Backend API calls
└── src/types/stock.ts         # TypeScript types
```

## 🚨 Troubleshooting

**Backend not connecting?**
- Check: `curl http://localhost:8080/health`
- Restart: `docker-compose down && docker-compose up -d`

**Frontend errors?**
- Install Node.js 18+
- Run: `npm install` in `frontend-nextjs/`
- Clear cache: `rm -rf .next node_modules && npm install`

## 🎯 Next Steps

1. **Customize the UI** - Edit Tailwind classes
2. **Add more pages** - Create in `src/app/`
3. **Enhance API** - Add endpoints to Go backend
4. **Deploy** - Use Vercel for frontend, any host for backend

## 💡 Why This Stack?

- **Go + Next.js** = Most in-demand skill combo
- **TypeScript** = Better than plain JavaScript
- **Tailwind** = Faster than writing CSS
- **Docker** = Consistent development environment

**You now have a modern, professional full-stack application! 🎉** 