import argparse

parser = argparse.ArgumentParser(description="test")
group = parser.add_mutually_exclusive_group()
group.add_argument('--test', dest='test', action='store')
group.add_argument('--preset', dest='preset', type=int, choices=[1, 2])
args = parser.parse_args()
print(args.preset)
print(args.test)
