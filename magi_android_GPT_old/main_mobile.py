try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


from ui.mobile import MAGIMobile

if __name__ == "__main__":

    MAGIMobile().run()