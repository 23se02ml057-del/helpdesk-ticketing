from werkzeug.security import generate_password_hash, check_password_hash

def test():
    pw = "Password!123"
    h = generate_password_hash(pw)
    print("Hash length:", len(h))
    print("Hash:", h)
    
    # Try verifying
    valid = check_password_hash(h, pw)
    print("Is valid:", valid)

if __name__ == '__main__':
    test()
