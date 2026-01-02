# apps/api/src/api/scripts/create_stripe_products.py
"""Script to create/update Stripe products and prices from plan data"""
import sys
import os
from pathlib import Path

# Add the src directory to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from api.core.database import SessionLocal
from api.services.stripe_service import StripeService


def main():
    """Create/update Stripe products and prices"""
    # Check required environment variables
    required_env_vars = ["STRIPE_SECRET_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before running this script.")
        sys.exit(1)

    stripe_service = StripeService()

    with SessionLocal() as db:
        print("Creating/updating Stripe products and prices...")
        results = stripe_service.create_or_update_products_and_prices(db)

        print("\n=== Results ===")

        if results["created"]:
            print(f"\nCreated ({len(results['created'])}):")
            for item in results["created"]:
                print(f"  - {item}")

        if results["updated"]:
            print(f"\nUpdated ({len(results['updated'])}):")
            for item in results["updated"]:
                print(f"  - {item}")

        if results["errors"]:
            print(f"\nErrors ({len(results['errors'])}):")
            for error in results["errors"]:
                print(f"  - {error}")
            sys.exit(1)

        print("\nSuccessfully processed all plans!")


if __name__ == "__main__":
    main()
