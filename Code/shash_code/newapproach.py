import pdfplumber
import pandas as pd

def extract_tables_from_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        all_tables = []
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table in tables:
                df = pd.DataFrame(table)
                df.dropna(how='all', axis=0, inplace=True)
                df.dropna(how='all', axis=1, inplace=True)
                all_tables.append(df)
                print(f"Table found on page {page_num + 1}:\n", df, "\n")
    return all_tables

def main():
    pdf_path = input("Enter the path to the PDF file: ")
    try:
        tables = extract_tables_from_pdf(pdf_path)
        if tables:
            save_tables = input("Do you want to save the extracted tables? (yes/no): ").strip().lower()
            if save_tables == 'yes':
                for i, table in enumerate(tables):
                    csv_path = f"table_{i + 1}.csv"
                    table.to_csv(csv_path, index=False)
                    print(f"Table {i + 1} saved as {csv_path}")
            else:
                print("Tables not saved.")
        else:
            print("No tables found in the PDF.")
    except FileNotFoundError:
        print("File not found. Please check the path and try again.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
