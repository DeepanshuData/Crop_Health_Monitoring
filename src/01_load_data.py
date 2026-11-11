
import pandas as pd

# Load the spectral reflectance dataset
df = pd.read_csv("data/five_city_spectral_reflectance.csv")

# Display first five records
print("\nFIRST FIVE ROWS")
print(df.head())

# Check dataset dimensions
print("\nDATASET SHAPE")
print(df.shape)

# Check column names
print("\nCOLUMN NAMES")
print(df.columns.tolist())

# Dataset information
print("\nDATASET INFORMATION")
df.info()

# Check missing values
print("\nMISSING VALUES")
print(df.isnull().sum())

# Check duplicate records
print("\nDUPLICATE RECORDS")
print(df.duplicated().sum())

# Count samples by city
print("\nSAMPLES PER CITY")
print(df["City"].value_counts())

# Count samples by land-cover class
print("\nSAMPLES PER LAND-COVER CLASS")
print(df["Land_Cover"].value_counts())
