from pdf2image import convert_from_path
import os
from pathlib import Path

def convert_pdf_to_jpg(pdf_path):
    try:
        # Convert PDF path to Path object
        pdf_path = Path(pdf_path)
        
        # Check if file exists and is a PDF
        if not pdf_path.exists():
            raise FileNotFoundError("The specified PDF file does not exist.")
        if pdf_path.suffix.lower() != '.pdf':
            raise ValueError("The specified file is not a PDF.")
        
        # Convert PDF to images
        images = convert_from_path(pdf_path)
        
        # Create output path (same directory as PDF)
        output_base = pdf_path.parent / pdf_path.stem
        
        # Save each page as JPG
        for i, image in enumerate(images, start=1):
            output_path = f"{output_base}_page_{i:02d}.jpg"
            image.save(output_path, 'JPEG')
            print(f"Saved page {i} as: {output_path}")
            
        print(f"\nSuccessfully converted {len(images)} pages to JPG format.")
        
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    print("PDF to JPG Converter")
    print("===================")
    
    # Get PDF path from user
    pdf_path = input("Please enter the path to your PDF file: ").strip()
    
    # Convert the PDF
    convert_pdf_to_jpg(pdf_path)

if __name__ == "__main__":
    main() 