# Claude Code Configuration - Standard Development Environment

## 📋 Project Overview
This Django project follows standard development practices with clean architecture principles.

### 🏗️ Project Structure
- **Django Apps**: Modular application design
- **Static Files**: CSS, JavaScript, and media assets
- **Templates**: HTML templates with Django template language
- **Database**: SQLite for development, PostgreSQL for production

### 🚀 Standard Build Commands
- `python manage.py runserver`: Start development server
- `python manage.py migrate`: Apply database migrations
- `python manage.py collectstatic`: Collect static files
- `python manage.py test`: Run test suite

### 📁 Key Applications
- **streamrec**: Multi-stream video recording application
- **makeads**: Advertisement management system
- **somi_plan**: Planning and scheduling system
- **email_templates**: Email template management

### 🔧 Development Guidelines
- Follow Django best practices
- Keep files under 500 lines
- Write tests for new functionality
- Use meaningful commit messages
- Never commit sensitive data

### 🎯 Code Style
- Follow PEP 8 for Python code
- Use Django coding standards
- Document complex functionality
- Maintain clean imports

### 📊 Testing
- Write unit tests for models and views
- Test user authentication flows
- Validate form inputs and outputs
- Test API endpoints

### 🔐 Security
- Never hardcode secrets
- Use environment variables for sensitive data
- Validate all user inputs
- Follow Django security guidelines

### 🚀 Deployment
- Use `collectstatic` before deployment
- Apply migrations in production
- Set DEBUG=False in production
- Use proper logging configuration

---

**📅 Last Updated: 2025-08-20**
**🛠️ Standard Django Development Environment**