# Edge Service GitHub Action

A GitHub Actions plugin that abstracts the Edge Service Platform's OpenAPI endpoints for package management and deployment. This action enables you to package, upload, and deploy applications to edge nodes using modular workflows.

## Features

- **Modular Workflows**: Execute `upload`, `deploy`, or both in any order
- **Package Management**: Create and upload tar.gz packages with flexible file patterns
- **Multi-Node Deployment**: Deploy to multiple edge nodes simultaneously  
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Package Validation**: Validates `edge.json` configuration and script files
- **Cross-Platform**: Supports Linux, macOS, and Windows runners

## Usage

### Basic Examples

#### Upload Only
```yaml
- name: Upload Package
  uses: WENETVIETNAM/edge-action@main
  with:
    api_token: ${{ secrets.EDGE_SERVICE_TOKEN }}
    workflow: 'upload'
    base_url: 'https://skillx.cloud'
    package_path: './dist'
    package_name: 'my-app'
    package_tag: 'v1.0.0'
    exclude_patterns: '*.log,node_modules'
```

#### Deploy Only (Existing Package)
```yaml
- name: Deploy Package
  uses: WENETVIETNAM/edge-action@main
  with:
    api_token: ${{ secrets.EDGE_SERVICE_TOKEN }}
    workflow: 'deploy'
    base_url: 'https://skillx.cloud'
    package_name: 'my-app'
    package_tag: 'v1.0.0'
    node_ids: 'bc9ebeb1-96a4-4dfd-953e-899a61637577,dd8fef2a-45b6-4c8e-9f21-123456789abc'
```

#### Upload and Deploy
```yaml  
- name: Upload and Deploy Package
  uses: WENETVIETNAM/edge-action@main
  with:
    api_token: ${{ secrets.EDGE_SERVICE_TOKEN }}
    workflow: 'upload,deploy'
    base_url: 'https://staging.skillx.cloud'
    package_path: './build'
    package_name: 'my-service'
    package_tag: ${{ github.sha }}
    include_patterns: '*.py,*.json,requirements.txt'
    node_ids: 'bc9ebeb1-96a4-4dfd-953e-899a61637577'
```

### Complete CI/CD Workflow Example

```yaml
name: Deploy to Edge

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v3
      
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        
    - name: Install dependencies
      run: npm install
      
    - name: Build application
      run: npm run build
      
    - name: Deploy to Edge Service
      uses: WENETVIETNAM/edge-action@main
      with:
        api_token: ${{ secrets.EDGE_SERVICE_TOKEN }}
        workflow: 'upload,deploy'
        base_url: 'https://skillx.cloud'
        package_path: './dist'
        package_name: 'my-webapp'
        package_tag: ${{ github.sha }}
        exclude_patterns: '*.map,*.test.js'
        node_ids: ${{ secrets.PRODUCTION_NODES }}
      id: deploy
      
    - name: Display deployment results
      run: |
        echo "Package ID: ${{ steps.deploy.outputs.upload_package_id }}"
        echo "Deployment IDs: ${{ steps.deploy.outputs.deploy_deployment_ids }}"
        echo "Deploy Status: ${{ steps.deploy.outputs.deploy_status }}"
```

## Inputs

### Required Inputs

| Input | Description |
|-------|-------------|
| `api_token` | Bearer token for API authentication |
| `workflow` | Comma-separated workflow steps (e.g., `"upload"`, `"deploy"`, `"upload,deploy"`) |

### Optional Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `base_url` | Platform base URL | `https://skillx.cloud` |

### Package-related Inputs
*Required when workflow includes `upload`*

| Input | Description |
|-------|-------------|
| `package_path` | Path to the directory/files to package |
| `package_name` | Name for the package |
| `package_tag` | Version tag for the package |
| `include_patterns` | Comma-separated glob patterns for files to include (defaults to all files if not specified) |
| `exclude_patterns` | Comma-separated glob patterns for files to exclude (defaults to all files if not specified) |

### Deployment-related Inputs
*Required when workflow includes `deploy`*

| Input | Description |
|-------|-------------|
| `node_ids` | Comma-separated string of node UUIDs to deploy to |

## Outputs

### Upload Outputs
*Available when workflow includes `upload`*

| Output | Description |
|--------|-------------|
| `upload_package_id` | ID of the uploaded package |
| `upload_package_url` | URL of the uploaded package file |
| `upload_status` | Upload success/failure status |

### Deployment Outputs
*Available when workflow includes `deploy`*

| Output | Description |
|--------|-------------|
| `deploy_deployment_ids` | JSON array of created deployment IDs |
| `deploy_deployment_summary` | JSON object with deployment results per node |
| `deploy_status` | Overall deployment status (`success`, `partial`, `failed`) |

## Package Requirements

Your package must include an `edge.json` file at the root level:

```json
{
  "script_path": "run.sh"
}
```

The `script_path` must point to an executable script (`.sh`, `.bash`) or binary file within your package.

### Example Package Structure

```
my-package/
├── edge.json
├── run.sh
├── app.py
├── requirements.txt
└── config/
    └── settings.json
```

## Workflow Steps

### Supported Steps

- `upload`: Package and upload application to the platform
- `deploy`: Deploy uploaded packages to specified edge nodes  
- `push`: Push package to container registry (future feature)

### Execution Order

Steps execute in the order specified in the `workflow` input:

- `"upload"` - Upload only
- `"deploy"` - Deploy only (package must exist)
- `"upload,deploy"` - Upload then deploy
- `"deploy,upload"` - Deploy then upload (will fail if package doesn't exist)
- `"push,upload,deploy"` - Future: Push to registry, upload to platform, then deploy

## Error Handling

The action includes comprehensive error handling:

- **Validation Errors**: Input validation with clear error messages
- **Package Errors**: Missing `edge.json`, invalid structure, missing script files
- **API Errors**: Authentication failures, network errors, server errors
- **Retry Logic**: Automatic retry with exponential backoff (max 3 attempts)
- **Partial Deployments**: Reports success/failure per node

## Environment Support

### Base URLs

- **Production**: `https://skillx.cloud`
- **Staging**: `https://staging.skillx.cloud`
- **Development**: `http://localhost:8000`

### Runners

Tested and supported on:
- `ubuntu-latest`
- `ubuntu-20.04`
- `ubuntu-18.04`
- `macos-latest`
- `windows-latest`

## API Endpoints

This action uses the following Edge Service API endpoints:

- `POST /public/edge-service/open-api/v1/packages/` - Package upload
- `GET /public/edge-service/open-api/v1/packages/` - Package search
- `POST /public/edge-service/open-api/v1/deployments/` - Create deployment

## Security

- API tokens are securely handled and never logged
- All API requests use HTTPS
- Input validation prevents injection attacks
- Temporary package files are cleaned up after upload

## Troubleshooting

### Common Issues

1. **"API token is required"**
   - Ensure `EDGE_SERVICE_TOKEN` is set in repository secrets
   - Verify the secret name matches your workflow file

2. **"Package path does not exist"**
   - Check that `package_path` points to existing directory
   - Ensure build steps complete before running this action

3. **"edge.json file not found"**
   - Add `edge.json` to your package root
   - Verify JSON format and required `script_path` field

4. **"Authentication failed"**
   - Verify API token is valid and not expired
   - Check that token has required permissions

5. **"Package not found" during deploy**
   - Ensure package was uploaded successfully
   - Verify `package_name` and `package_tag` match exactly

### Debug Mode

Enable debug logging by setting:

```yaml
env:
  ACTIONS_STEP_DEBUG: true
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue in this repository
- Check the Edge Service Platform documentation
- Contact support at support@skillx.cloud