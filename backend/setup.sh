#!/bin/bash

# Tuppence Backend Setup Script
# This script sets up the local development environment

set -e

echo "🎬 Setting up Tuppence Backend..."

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "✅ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "⚙️  Please edit .env with your DATABASE_URL and OPENAI_API_KEY"
    echo "   DATABASE_URL example: postgresql://user:password@localhost:5432/tuppence"
    echo "   OPENAI_API_KEY: Get from https://platform.openai.com/api-keys"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your database credentials and OpenAI API key"
echo "2. Run: source venv/bin/activate"
echo "3. Run: alembic upgrade head"
echo "4. Run: uvicorn app.main:app --reload"
echo ""
echo "Server will be available at http://localhost:8000"
echo "API docs at http://localhost:8000/docs"
