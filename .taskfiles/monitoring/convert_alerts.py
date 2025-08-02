#!/usr/bin/env python3

import yaml
import json
import os
import sys
import argparse
from pathlib import Path


def convert_value_to_vmrule_format(value, indent_level=0):
    """Convert a value to VMRule quoted string format with proper indentation."""
    indent = "  " * indent_level

    if isinstance(value, dict):
        result = "\n"
        for k, v in value.items():
            result += f'{indent}"{k}":'
            if isinstance(v, (dict, list)):
                result += convert_value_to_vmrule_format(v, indent_level + 1)
            else:
                # Use | for multiline strings, |- for single line
                if isinstance(v, str) and ('\n' in str(v) or len(str(v)) > 80):
                    result += " |\n"
                else:
                    result += " |-\n"
                # Handle multiline strings properly
                str_value = str(v)
                for line in str_value.splitlines():
                    result += f"{indent}  {line}\n"
        return result

    elif isinstance(value, list):
        result = "\n"
        for item in value:
            result += f"{indent}- "  # Important: space after the dash
            if isinstance(item, (dict, list)):
                # For dict/list items, we need proper formatting
                item_result = convert_value_to_vmrule_format(item, indent_level + 1)
                # Remove the leading newline and adjust indentation
                item_lines = item_result.strip().split('\n')
                for i, line in enumerate(item_lines):
                    if i == 0:
                        result += line + "\n"
                    else:
                        result += f"{indent}  {line}\n"
            else:
                result += f"|-\n{indent}  {item}\n"
        return result

    else:
        return f"|-\n{indent}  {value}\n"


def convert_alert_file(input_file, output_dir):
    """Convert a single alert file to VMRule format."""
    input_path = Path(input_file)
    # Add -rules suffix to the name
    output_name = f"{input_path.stem}-rules"
    output_path = Path(output_dir) / f"{output_name}.yaml"

    print(f"Converting: {input_file} -> {output_path}")

    # Read the input file
    with open(input_path, 'r') as f:
        content = f.read()

    # Remove leading --- if present
    if content.startswith('---'):
        content = content[3:].lstrip()

    # Parse the YAML content
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {input_file}: {e}")
        return False

    # Generate VMRule YAML
    vmrule_content = f"""apiVersion: operator.victoriametrics.com/v1beta1
kind: VMRule
metadata:
  name: {output_name}
  namespace: monitoring
spec:
"""

    # Convert the data to VMRule format
    for key, value in data.items():
        vmrule_content += f'  "{key}":'
        vmrule_content += convert_value_to_vmrule_format(value, 1)

    # Write the output file
    with open(output_path, 'w') as f:
        f.write(vmrule_content)

    print(f"Created: {output_path}")
    return True


def generate_kustomization(output_dir):
    """Generate kustomization.yaml file for all VMRule files."""
    output_path = Path(output_dir)
    kustomization_path = output_path / "kustomization.yaml"

    # Find all YAML files except kustomization.yaml
    yaml_files = [f for f in output_path.glob("*.yaml") if f.name != "kustomization.yaml"]

    if not yaml_files:
        print("Warning: No YAML files found to add to kustomization.yaml")
        return False

    # Generate kustomization content
    kustomization_content = """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
"""

    for yaml_file in sorted(yaml_files):
        kustomization_content += f"- {yaml_file.name}\n"
        print(f"Added to kustomization: {yaml_file.name}")

    # Write kustomization.yaml
    with open(kustomization_path, 'w') as f:
        f.write(kustomization_content)

    print(f"Generated: {kustomization_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Convert alert files to VictoriaMetrics VMRule format")
    parser.add_argument("--input-dir", required=True, help="Directory containing alert files")
    parser.add_argument("--output-dir", required=True, help="Output directory for VMRule files")
    parser.add_argument("--clean", action="store_true", help="Clean output directory before conversion")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Validate input directory
    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean output directory if requested
    if args.clean:
        for file in output_dir.glob("*"):
            if file.is_file():
                file.unlink()
        print(f"Cleaned output directory: {output_dir}")

    # Find alert files (YAML and JSON)
    alert_files = list(input_dir.glob("*.yaml")) + list(input_dir.glob("*.yml")) + list(input_dir.glob("*.json"))

    if not alert_files:
        print(f"No alert files found in {input_dir}")
        sys.exit(1)

    print(f"Found {len(alert_files)} alert files in {input_dir}")

    # Convert each file
    success_count = 0
    for alert_file in alert_files:
        if convert_alert_file(alert_file, output_dir):
            success_count += 1

    print(f"Successfully converted {success_count}/{len(alert_files)} files")

    # Generate kustomization.yaml
    if success_count > 0:
        generate_kustomization(output_dir)

    print("Conversion complete!")


if __name__ == "__main__":
    main()
