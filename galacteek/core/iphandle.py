import re

ipHandleRe = re.compile(
    r"^\w{1,32}(\#[0-9]{1,9})?@\w{1,64}$"
)
