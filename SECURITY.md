# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of DossieClean seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### How to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **GitHub Security Advisories**: Use the "Report a vulnerability" button in the Security tab of the repository
2. **Email**: Contact the maintainers directly (check the repository for contact information)

### What to Include

Please include the following information in your report:

- Type of vulnerability (e.g., SQL injection, XSS, authentication bypass)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability and how an attacker might exploit it

### Response Timeline

- **Initial Response**: Within 48 hours, we will acknowledge receipt of your report
- **Status Update**: Within 7 days, we will provide an initial assessment
- **Resolution**: We aim to resolve critical vulnerabilities within 30 days

### What to Expect

- We will confirm the vulnerability and determine its impact
- We will release a fix as soon as possible, depending on complexity
- We will publicly acknowledge your responsible disclosure (unless you prefer to remain anonymous)

## Security Best Practices for Deployment

When deploying DossieClean, please follow these security best practices:

### Environment Variables

- **Never commit `.env` files** to version control
- Use strong, unique values for `SECRET_KEY`
- Rotate API keys regularly
- Use environment-specific credentials (dev vs. production)

### API Keys

- Store API keys securely using environment variables or a secrets manager
- Use the principle of least privilege for API key permissions
- Monitor API key usage for unusual activity

### Network Security

- Always use HTTPS in production
- Configure proper CORS settings
- Use a reverse proxy (nginx, Apache) in production
- Implement rate limiting to prevent abuse

### File Uploads

- The application validates file types (PDF only)
- Uploaded files are stored temporarily and cleaned up after processing
- Consider implementing virus scanning for uploaded files in production

### Database Security

- Use strong passwords for database connections
- Enable SSL/TLS for database connections
- Regularly backup your data
- Use the principle of least privilege for database users

### Azure Blob Storage

- Use SAS tokens with minimal permissions when possible
- Enable Azure Storage encryption
- Configure proper access policies
- Monitor storage account activity

### Qdrant Vector Database

- Use API key authentication
- Enable TLS for connections
- Restrict network access to trusted sources

## Known Security Considerations

### Current Limitations

1. **No Built-in Authentication**: The application does not include user authentication. Implement authentication at the reverse proxy level or add authentication middleware before deploying publicly.

2. **Session Security**: Flask sessions are used for temporary data storage. Ensure `SECRET_KEY` is strong and unique in production.

3. **File Processing**: Large PDF files are processed in memory. Monitor server resources to prevent denial of service.

### Recommended Additional Security Measures

- Implement user authentication and authorization
- Add request rate limiting
- Enable audit logging
- Set up intrusion detection
- Regular security audits and penetration testing

## Acknowledgments

We appreciate the security research community and thank all researchers who responsibly disclose vulnerabilities to us.
