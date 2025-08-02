#!/usr/bin/env python3

import os
import yaml
import sys
import shutil
import glob
import subprocess

def main():
    AlertManifestGenerator()

class AlertManifestGenerator():

    DESTINATION_DIRECTORY = "kubernetes/apps/monitoring/victoriametrics/alerts"
    SOURCE_DIRECTORY = "alerts"
    TEMPLATES_DIRECTORY = "templates"

    def __init__(self):
        self.purge_manifests()
        self.generate_manifests()

    def purge_manifests(self):
        if os.path.exists(self.DESTINATION_DIRECTORY):
            shutil.rmtree(self.DESTINATION_DIRECTORY, ignore_errors=True)

        os.makedirs(self.DESTINATION_DIRECTORY, exist_ok=True)

    def generate_manifests(self):
        print(f"Converting alerts from {self.SOURCE_DIRECTORY} to {self.DESTINATION_DIRECTORY}")

        # Check if source directory exists
        if not os.path.exists(self.SOURCE_DIRECTORY):
            print(f"Error: Source directory {self.SOURCE_DIRECTORY} does not exist")
            sys.exit(1)

        # Find all YAML alert files
        alert_files = []
        alert_files.extend(glob.glob(os.path.join(self.SOURCE_DIRECTORY, "*.yaml")))
        alert_files.extend(glob.glob(os.path.join(self.SOURCE_DIRECTORY, "*.yml")))

        if not alert_files:
            print(f"No alert files found in {self.SOURCE_DIRECTORY}")
            sys.exit(1)

        print(f"Found {len(alert_files)} alert files")

        # Process each alert file
        for alert_file in alert_files:
            self.process_alert_file(alert_file)

        # Generate kustomization.yaml
        self.write_kustomization()

    def process_alert_file(self, alert_file):
        """
        Process a single alert file and generate VMRule manifest using makejinja
        """
        print(f"Processing: {alert_file}")

        try:
            with open(alert_file, "r") as file:
                content = file.read()

                # Remove leading --- if present
                if content.startswith('---'):
                    content = content[3:].lstrip()

                yaml_content = yaml.safe_load(content)

                # Extract name from filename and add -rules suffix
                base_name = os.path.splitext(os.path.basename(alert_file))[0]
                name = f"{base_name}-rules"

                # Convert YAML to string with proper formatting
                rule_yaml = yaml.safe_dump(yaml_content, default_style="|")

                # Create VMRule content manually (since we want to avoid jinja2 dependency)
                vmrule_content = f"""apiVersion: operator.victoriametrics.com/v1beta1
kind: VMRule
metadata:
  name: {name}
  namespace: monitoring
spec:
  {self.indent_yaml(rule_yaml, 2)}"""

                # Write the output file
                output_file = os.path.join(self.DESTINATION_DIRECTORY, f"{name}.yaml")
                with open(output_file, "w") as f:
                    f.write(vmrule_content)

                print(f"Created: {output_file}")

        except Exception as e:
            print(f"Error processing {alert_file}: {e}")
            sys.exit(1)

    def indent_yaml(self, yaml_string, spaces):
        """
        Indent each line of YAML string by specified number of spaces, except the first line
        """
        lines = yaml_string.split('\n')
        indented_lines = []

        for i, line in enumerate(lines):
            if i == 0:
                # Don't indent the first line
                indented_lines.append(line)
            elif line.strip():  # Don't indent empty lines
                indented_lines.append(' ' * spaces + line)
            else:
                indented_lines.append(line)

        return '\n'.join(indented_lines)

    def write_kustomization(self):
        """
        Generate kustomization.yaml file
        """
        print("Generating kustomization.yaml...")

        try:
            # Get all YAML files except kustomization.yaml
            files = [f for f in os.listdir(self.DESTINATION_DIRECTORY)
                    if f.endswith('.yaml') and f != 'kustomization.yaml']

            if not files:
                print("Warning: No YAML files found to add to kustomization.yaml")
                return

            # Create kustomization content
            kustomization_content = """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
"""

            for filename in sorted(files):
                kustomization_content += f"- {filename}\n"

            # Write kustomization.yaml
            output_file = os.path.join(self.DESTINATION_DIRECTORY, "kustomization.yaml")
            with open(output_file, "w") as f:
                f.write(kustomization_content)

            print(f"Generated: {output_file}")

        except Exception as e:
            print(f"Error generating kustomization.yaml: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
