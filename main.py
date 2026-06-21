#!/usr/bin/env python3
import sys
from app import PrayerApplication

def main():
    app = PrayerApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
