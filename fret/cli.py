from .app import get_app


def main(args=None):
    return get_app().main(args)


if __name__ == '__main__':
    main()
