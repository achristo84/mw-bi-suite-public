#!/usr/bin/env python3
"""
Test script for invoice parsing service.
Tests parsing of sample invoices without database integration.

Usage:
    python3 scripts/test_invoice_parser.py
    python3 scripts/test_invoice_parser.py --file sample_pdf/pfs_bur_inv251211518599.pdf
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_parse_single_file(file_path: str):
    """Parse a single PDF and display results."""
    print(f"\n{'='*60}")
    print(f"Parsing: {file_path}")
    print('='*60)

    from app.services.invoice_parser import get_invoice_parser

    parser = get_invoice_parser()

    with open(file_path, "rb") as f:
        pdf_content = f.read()

    try:
        result = parser.parse_invoice(pdf_content)

        print(f"\n📄 Invoice Number: {result.invoice_number}")
        print(f"📅 Invoice Date: {result.invoice_date}")
        print(f"📅 Delivery Date: {result.delivery_date}")
        print(f"📅 Due Date: {result.due_date}")
        print(f"👤 Account #: {result.account_number}")
        print(f"👤 Sales Rep: {result.sales_rep_name}")
        print(f"📋 SO #: {result.sales_order_number}")
        print(f"\n💰 Subtotal: ${result.subtotal_cents/100:.2f}" if result.subtotal_cents else "\n💰 Subtotal: N/A")
        print(f"💰 Tax: ${result.tax_cents/100:.2f}" if result.tax_cents else "💰 Tax: N/A")
        print(f"💰 Total: ${result.total_cents/100:.2f}")
        print(f"\n🎯 Confidence: {result.confidence:.0%}")

        print(f"\n📦 Line Items ({len(result.line_items)}):")
        print("-" * 80)

        for i, item in enumerate(result.line_items, 1):
            sku = item.get('raw_sku') or 'N/A'
            desc = item.get('raw_description', 'Unknown')[:40]
            qty = item.get('quantity') or 0
            unit_price = (item.get('unit_price_cents') or 0) / 100
            ext_price = (item.get('extended_price_cents') or 0) / 100
            line_type = item.get('line_type', 'product')

            type_icon = "📦" if line_type == "product" else "💳" if line_type == "credit" else "📋"

            print(f"{i:2}. {type_icon} [{sku:10}] {desc:40} x{qty:6.1f} @ ${unit_price:8.2f} = ${ext_price:9.2f}")

            if item.get('parent_sku'):
                print(f"      ↳ Applied to: {item['parent_sku']}")

        print("-" * 80)

        # Verify totals
        line_total = sum(item.get('extended_price_cents', 0) for item in result.line_items)
        print(f"\nLine items sum: ${line_total/100:.2f}")
        if result.subtotal_cents:
            diff = abs(line_total - result.subtotal_cents)
            if diff > 1:  # Allow 1 cent rounding
                print(f"⚠️  Difference from subtotal: ${diff/100:.2f}")

        return result

    except Exception as e:
        print(f"\n❌ Error parsing invoice: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_all_samples():
    """Test parsing all sample PDFs."""
    sample_dir = Path(__file__).parent.parent / "sample_pdf"

    if not sample_dir.exists():
        print(f"Sample directory not found: {sample_dir}")
        return

    pdf_files = list(sample_dir.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in sample_pdf/")
        return

    print(f"Found {len(pdf_files)} sample PDFs to parse")

    results = []
    for pdf_file in pdf_files:
        result = test_parse_single_file(str(pdf_file))
        results.append((pdf_file.name, result))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for filename, result in results:
        if result:
            status = "✅"
            confidence = f"{result.confidence:.0%}"
            total = f"${result.total_cents/100:.2f}"
            lines = len(result.line_items)
        else:
            status = "❌"
            confidence = "N/A"
            total = "N/A"
            lines = 0

        print(f"{status} {filename:40} | Conf: {confidence:>4} | Total: {total:>10} | Lines: {lines}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Test invoice parsing')
    parser.add_argument('--file', '-f', type=str, help='Parse a specific file')
    parser.add_argument('--json', action='store_true', help='Output raw JSON response')
    args = parser.parse_args()

    if args.file:
        result = test_parse_single_file(args.file)
        if args.json and result:
            print("\n📄 Raw JSON response:")
            print(result.raw_response)
    else:
        test_all_samples()


if __name__ == '__main__':
    main()
