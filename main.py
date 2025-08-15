#!/usr/bin/env python3
"""
Edge Service GitHub Action
A GitHub Actions plugin for Edge Service Platform package management and deployment.
"""

import os
import sys
import json
import tarfile
import tempfile
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any


class EdgeServiceAction:
    def __init__(self):
        self.api_token = os.getenv('INPUT_API_TOKEN')
        self.workflow = os.getenv('INPUT_WORKFLOW', '')
        self.base_url = os.getenv('INPUT_BASE_URL')
        
        # Package inputs
        self.package_path = os.getenv('INPUT_PACKAGE_PATH')
        self.package_name = os.getenv('INPUT_PACKAGE_NAME')
        self.package_tag = os.getenv('INPUT_PACKAGE_TAG')
        
        # Deployment inputs
        self.node_ids = os.getenv('INPUT_NODE_IDS')
        
        # Registry inputs (future)
        self.registry_url = os.getenv('INPUT_REGISTRY_URL')
        self.registry_username = os.getenv('INPUT_REGISTRY_USERNAME')
        self.registry_password = os.getenv('INPUT_REGISTRY_PASSWORD')
        
        # Pattern inputs
        self.include_patterns = os.getenv('INPUT_INCLUDE_PATTERNS')
        self.exclude_patterns = os.getenv('INPUT_EXCLUDE_PATTERNS')
        
        # Validation
        self._validate_inputs()
    
    def _validate_inputs(self):
        """Validate required inputs based on workflow"""
        if not self.api_token:
            self.error("API token is required")
            
        if not self.workflow:
            self.error("Workflow is required")
            
        workflow_steps = self.parse_workflow(self.workflow)
        
        # Validate package-related inputs for upload/push
        if any(step in workflow_steps for step in ['upload', 'push']):
            if not all([self.package_path, self.package_name, self.package_tag]):
                self.error("package_path, package_name, and package_tag are required for upload/push workflows")
                
        # Validate deployment inputs
        if 'deploy' in workflow_steps:
            if not self.node_ids:
                self.error("node_ids is required for deploy workflow")
            if not self.package_name or not self.package_tag:
                self.error("package_name and package_tag are required for deploy workflow")
                
        # Validate pattern exclusivity
        if self.include_patterns and self.exclude_patterns:
            self.error("include_patterns and exclude_patterns are mutually exclusive")
    
    def parse_workflow(self, workflow_string: str) -> List[str]:
        """Parse comma-separated workflow string into list of steps"""
        steps = [step.strip() for step in workflow_string.split(',')]
        valid_steps = ['push', 'upload', 'deploy']
        
        for step in steps:
            if step not in valid_steps:
                self.error(f"Invalid workflow step: {step}. Valid steps: {', '.join(valid_steps)}")
                
        return steps
    
    def execute_workflows(self) -> Dict[str, Any]:
        """Execute workflow steps in specified order"""
        steps = self.parse_workflow(self.workflow)
        results = {}
        
        self.log(f"Executing workflow steps: {', '.join(steps)}")
        
        for step in steps:
            self.log(f"Executing step: {step}")
            
            if step == 'push':
                results['push'] = self.execute_registry_push()
            elif step == 'upload':
                results['upload'] = self.execute_package_upload()
            elif step == 'deploy':
                results['deploy'] = self.execute_deployment(results.get('upload'))
                
        return results
    
    def execute_registry_push(self) -> Dict[str, Any]:
        """Execute registry push (future feature)"""
        self.log("Registry push functionality is not yet implemented")
        return {
            'status': 'skipped',
            'message': 'Registry push is a future feature'
        }
    
    def execute_package_upload(self) -> Dict[str, Any]:
        """Execute package upload workflow"""
        try:
            # Step 1: Validate package path
            if not os.path.exists(self.package_path):
                raise Exception(f"Package path does not exist: {self.package_path}")
            
            # Step 2: Create package archive
            package_file = self.create_package_archive()
            
            # Step 3: Validate package structure
            self.validate_package_structure(package_file)
            
            # Step 4: Upload package
            upload_result = self.upload_package_to_api(package_file)
            
            # Cleanup temporary file
            os.unlink(package_file)
            
            return upload_result
            
        except Exception as e:
            self.error(f"Package upload failed: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    def create_package_archive(self) -> str:
        """Create tar.gz archive of the package"""
        package_filename = f"{self.package_name}-{self.package_tag}.tar.gz"
        
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
            with tarfile.open(tmp_file.name, 'w:gz') as tar:
                package_path = Path(self.package_path)
                
                if self.include_patterns:
                    # Include specific patterns
                    patterns = [p.strip() for p in self.include_patterns.split(',')]
                    for pattern in patterns:
                        for file_path in package_path.rglob(pattern):
                            if file_path.is_file():
                                arcname = file_path.relative_to(package_path)
                                tar.add(file_path, arcname=arcname)
                                
                elif self.exclude_patterns:
                    # Exclude specific patterns
                    patterns = [p.strip() for p in self.exclude_patterns.split(',')]
                    for file_path in package_path.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(package_path)
                            # Check if file matches any exclude pattern
                            should_exclude = False
                            for pattern in patterns:
                                if file_path.match(pattern) or any(part.match(pattern) for part in file_path.parts):
                                    should_exclude = True
                                    break
                            if not should_exclude:
                                tar.add(file_path, arcname=arcname)
                else:
                    # Include all files
                    tar.add(package_path, arcname='.')
            
            return tmp_file.name
    
    def validate_package_structure(self, package_file: str):
        """Validate that package contains required edge.json"""
        with tarfile.open(package_file, 'r:gz') as tar:
            # Check if edge.json exists at root level
            edge_json_found = False
            for member in tar.getmembers():
                if member.name == 'edge.json' or member.name == './edge.json':
                    edge_json_found = True
                    # Extract and validate edge.json content
                    edge_json_file = tar.extractfile(member)
                    if edge_json_file:
                        try:
                            edge_config = json.loads(edge_json_file.read().decode('utf-8'))
                            if 'script_path' not in edge_config:
                                raise Exception("edge.json must contain 'script_path' key")
                            
                            script_path = edge_config['script_path']
                            if not script_path:
                                raise Exception("script_path cannot be empty")
                                
                            # Validate script file exists in archive
                            script_found = False
                            for script_member in tar.getmembers():
                                if script_member.name == script_path or script_member.name == f'./{script_path}':
                                    script_found = True
                                    break
                            
                            if not script_found:
                                raise Exception(f"Script file '{script_path}' not found in package")
                                
                        except json.JSONDecodeError as e:
                            raise Exception(f"Invalid JSON in edge.json: {str(e)}")
                    break
            
            if not edge_json_found:
                raise Exception("edge.json file not found at root level of package")
    
    def upload_package_to_api(self, package_file: str) -> Dict[str, Any]:
        """Upload package to the API with upsert functionality"""
        url = f"{self.base_url}/public/edge-service/open-api/v1/packages/"
        
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json'
        }
        
        files = {
            'package_file': open(package_file, 'rb')
        }
        
        data = {
            'name': self.package_name,
            'tag': self.package_tag,
            'upsert': 'true'
        }
        
        response = self.make_request_with_retry('POST', url, headers=headers, files=files, data=data)
        
        if response.status_code in [200, 201]:
            result = response.json()
            was_updated = response.status_code == 200
            action = "updated" if was_updated else "created"
            self.log(f"Package {action} successfully. Package ID: {result['id']}")
            return {
                'status': 'success',
                'package_id': result['id'],
                'package_url': result['package_file'],
                'was_updated': was_updated,
                'response': result
            }
        else:
            raise Exception(f"Upload failed with status {response.status_code}: {response.text}")
    
    def execute_deployment(self, upload_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute deployment workflow"""
        try:
            # Get package ID
            if upload_result and upload_result.get('package_id'):
                package_id = upload_result['package_id']
                self.log(f"Using package ID from upload: {package_id}")
            else:
                package_id = self.get_package_id_by_name_tag()
                self.log(f"Retrieved package ID by name/tag: {package_id}")
            
            # Parse node IDs
            node_id_list = [node_id.strip() for node_id in self.node_ids.split(',')]
            
            # Deploy to each node
            deployment_results = []
            deployment_ids = []
            
            for node_id in node_id_list:
                self.log(f"Deploying to node: {node_id}")
                deployment_result = self.deploy_to_node(package_id, node_id)
                deployment_results.append({
                    'node_id': node_id,
                    'deployment_id': deployment_result.get('id'),
                    'status': 'success' if deployment_result else 'failed',
                    'result': deployment_result
                })
                if deployment_result and deployment_result.get('id'):
                    deployment_ids.append(deployment_result['id'])
            
            success_count = len([r for r in deployment_results if r['status'] == 'success'])
            total_count = len(deployment_results)
            
            return {
                'status': 'success' if success_count == total_count else 'partial',
                'deployment_ids': deployment_ids,
                'deployment_summary': deployment_results,
                'success_count': success_count,
                'total_count': total_count
            }
            
        except Exception as e:
            self.error(f"Deployment failed: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    def get_package_id_by_name_tag(self) -> int:
        """Retrieve package ID by name and tag"""
        url = f"{self.base_url}/public/edge-service/open-api/v1/packages/"
        
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json'
        }
        
        params = {
            'name': self.package_name,
            'tag': self.package_tag
        }
        
        response = self.make_request_with_retry('GET', url, headers=headers, params=params)
        
        if response.status_code == 200:
            result = response.json()
            if result['count'] > 0:
                return result['results'][0]['id']
            else:
                raise Exception(f"Package not found: {self.package_name}:{self.package_tag}")
        else:
            raise Exception(f"Failed to retrieve package with status {response.status_code}: {response.text}")
    
    def deploy_to_node(self, package_id: int, node_id: str) -> Dict[str, Any]:
        """Deploy package to a specific node"""
        url = f"{self.base_url}/public/edge-service/open-api/v1/deployments/"
        
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        data = {
            'package_id': package_id,
            'node_id': node_id
        }
        
        response = self.make_request_with_retry('POST', url, headers=headers, json=data)
        
        if response.status_code == 201:
            result = response.json()
            self.log(f"Deployment created for node {node_id}. Deployment ID: {result['id']}")
            return result
        else:
            self.error(f"Deployment to node {node_id} failed with status {response.status_code}: {response.text}")
            return {}
    
    def make_request_with_retry(self, method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
        """Make HTTP request with exponential backoff retry logic"""
        for attempt in range(max_retries):
            try:
                response = requests.request(method, url, timeout=30, **kwargs)
                
                # Don't retry on authentication errors
                if response.status_code == 401:
                    raise Exception(f"Authentication failed: {response.text}")
                
                # Don't retry on client errors (4xx except 429)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    return response
                
                # Return successful responses
                if response.status_code < 400:
                    return response
                
                # Retry on server errors and 429
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    self.log(f"Request failed (status {response.status_code}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    return response
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    self.log(f"Request exception: {str(e)}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Request failed after {max_retries} attempts: {str(e)}")
        
        raise Exception(f"Request failed after {max_retries} attempts")
    
    def set_output(self, name: str, value: Any):
        """Set GitHub Actions output"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        # GitHub Actions output format
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"{name}={value}\n")
        else:
            # Fallback for local testing
            print(f"::set-output name={name}::{value}")
    
    def log(self, message: str):
        """Log message to stdout"""
        print(f"[INFO] {message}")
    
    def error(self, message: str):
        """Log error and exit"""
        print(f"[ERROR] {message}")
        sys.exit(1)
    
    def run(self):
        """Main execution method"""
        try:
            self.log("Starting Edge Service Action")
            self.log(f"Workflow: {self.workflow}")
            self.log(f"Base URL: {self.base_url}")
            
            results = self.execute_workflows()
            
            # Set outputs based on results
            for workflow_step, result in results.items():
                if workflow_step == 'upload' and result.get('status') == 'success':
                    self.set_output('upload_package_id', result.get('package_id'))
                    self.set_output('upload_package_url', result.get('package_url'))
                    self.set_output('upload_status', 'success')
                    self.set_output('upload_was_updated', result.get('was_updated', False))
                elif workflow_step == 'deploy' and result.get('status') in ['success', 'partial']:
                    self.set_output('deploy_deployment_ids', result.get('deployment_ids', []))
                    self.set_output('deploy_deployment_summary', result.get('deployment_summary', []))
                    self.set_output('deploy_status', result.get('status'))
                elif workflow_step == 'push':
                    self.set_output('push_status', result.get('status', 'skipped'))
            
            self.log("Edge Service Action completed successfully")
            
        except Exception as e:
            self.error(f"Action failed: {str(e)}")


if __name__ == "__main__":
    action = EdgeServiceAction()
    action.run()