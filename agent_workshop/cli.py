"""Run two demonstrations without external dependencies or accounts."""
import argparse, json
from .booking import BookingStore, Concierge, run_slot_race
from .mr_review import ReviewSupervisor


def main():
    parser = argparse.ArgumentParser(description="From Agent Demo to Production workshop")
    parser.add_argument('demo', choices=['booking', 'race', 'mr-risky', 'mr-clean', 'all'])
    args = parser.parse_args()
    if args.demo in ('booking', 'all'):
        concierge = Concierge(BookingStore())
        for who, msg, mid in [('customer-1', 'Book Dr Rao on Friday after 5 PM', 'sms-1'),
                             ('customer-1', 'YES', 'sms-2'),
                             ('customer-1', 'YES', 'sms-2'),
                             ('customer-2', 'I need a supervisor to call me', 'sms-3')]:
            result = concierge.on_message(who, msg, mid)
            print('\n' + who + ' > ' + msg)
            print(result.agent + ' > ' + result.message + ' [' + result.state + ']')
        print('Booking metrics:', json.dumps(concierge.store.summary(), indent=2))
    if args.demo in ('race', 'all'):
        print('\nSLOT RACE:', json.dumps(run_slot_race(20), indent=2))
    if args.demo in ('mr-risky', 'mr-clean', 'all'):
        review = ReviewSupervisor()
        scenarios = ['risky', 'clean'] if args.demo == 'all' else [args.demo.split('-')[1]]
        for name in scenarios:
            print('\nMERGE REQUEST REVIEW:', json.dumps(review.review(name), indent=2))


if __name__ == '__main__':
    main()
