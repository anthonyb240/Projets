import re

BAD_WORDS = [
    "connard", "salope", "merde", "putain", "enculé", "fils de pute",
    "faggot", "nigger", "bitch", "cunt", "asshole", "fuck", 
    "chier", "con", "pd", "nique"
]

def censor_text(text):
    if not text:
        return text
    
    censored_text = text
    for word in BAD_WORDS:
        # Create a regex representing the word with word boundaries, case insensitive
        # using \b to ensure we only replace full words if possible, but for simple profanity, 
        # sometimes we want to catch partials. For safety, let's just do full words to avoid Scunthorpe problem.
        pattern = r'\b' + re.escape(word) + r'\b'
        censored_text = re.sub(pattern, '***', censored_text, flags=re.IGNORECASE)
    
    return censored_text
