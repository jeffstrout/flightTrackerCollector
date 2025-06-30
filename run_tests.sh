#!/bin/bash

# Flight Tracker Backend Test Runner

echo "🧪 Running Flight Tracker Backend Tests..."
echo "========================================"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests with coverage
echo "Running unit tests with coverage..."
python -m pytest tests/ \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    -v

# Check if tests passed
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    echo ""
    echo "📊 Coverage report generated in htmlcov/index.html"
else
    echo ""
    echo "❌ Tests failed!"
    exit 1
fi

# Run type checking
echo ""
echo "Running type checking with mypy..."
python -m mypy src/ --ignore-missing-imports

# Run linting
echo ""
echo "Running linting with flake8..."
python -m flake8 src/ --max-line-length=100 --exclude=__pycache__

echo ""
echo "✨ Test run complete!"