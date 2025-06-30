# Car-nalytics Setup Guide

## Overview
Car-nalytics is a Flask web application for car parts segmentation and brand recognition. It uses YOLOv5 and SegFormer models for image processing and analysis.

## Prerequisites
- Python 3.7 or higher
- pip (Python package installer)
- Git (optional, for cloning)

## Step-by-Step Setup

### 1. Navigate to Project Directory
```bash
cd "Untitled"
```

### 2. Create Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirement.txt
```

### 4. Download Model Weights
The application requires pre-trained model weights that are not included in the repository:

1. **YOLOv5 Model**: Download from [Google Drive](https://drive.google.com/file/d/1-8tgADvOHK72j0D74YiuXU1qGhoBX3tF/view)
2. **SegFormer Model**: Download from [Google Drive](https://drive.google.com/drive/folders/1F3g58XMaDxYFDy6vmPdnaIrX_lBpS6mj)

3. **Place the downloaded model files in the `model_env/` directory**

### 5. Create Required Directories
```bash
# Create uploads directory
mkdir -p static/uploads
```

### 6. Set Up Email Configuration (Optional)
If you want to use email features, set these environment variables:
```bash
export MAIL_USERNAME="your-email@gmail.com"
export MAIL_PASSWORD="your-app-password"
```

## Running the Application

### Start the Web Server
```bash
python app.py
```

The application will start on:
- **URL**: http://localhost:3001
- **Host**: 0.0.0.0 (accessible from other devices on the network)
- **Port**: 3001
- **Debug Mode**: Enabled

### Access the Website
Open your web browser and navigate to:
```
http://localhost:3001
```

## Features
- **Home Page**: View uploaded car images and analysis results
- **Upload Page**: Upload car images for analysis
- **Car Analysis**: View detailed segmentation and brand recognition results
- **User Management**: Registration and login system
- **Email Notifications**: Optional email functionality

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Change the port in `app.py` line 385: `port=3002` (or any available port)

2. **Missing Model Files**
   - Ensure you've downloaded and placed the model weights in `model_env/` directory

3. **Import Errors**
   - Make sure all dependencies are installed: `pip install -r requirement.txt`
   - Activate your virtual environment if using one

4. **Permission Errors**
   - Ensure the `static/uploads` directory has write permissions

### Dependencies Added
The following dependencies were added to `requirement.txt`:
- `Flask-Limiter==3.3.0` - Rate limiting
- `Flask-Mail==0.9.1` - Email functionality
- `rembg==2.0.50` - Background removal
- `openpyxl==3.0.10` - Excel file handling

## Project Structure
```
Untitled/
├── app.py              # Main Flask application
├── configs.py          # Configuration settings
├── tools.py            # Utility functions
├── requirement.txt     # Python dependencies
├── model_env/          # AI models and configurations
├── static/             # Static files (CSS, JS, images)
├── templates/          # HTML templates
└── venv/              # Virtual environment (created during setup)
```

## Development
- The application runs in debug mode by default
- Changes to Python files will automatically reload the server
- Check the console for error messages and debugging information 