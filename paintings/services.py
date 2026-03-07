from .models import OTVET

def word_similarity(a, b):
    matches = 0
    for char in a:
        if char in b:
            matches += 1
    return matches / max(len(a), len(b))


def find_best_answer(question):
    question_words = question.lower().split()
    answers = OTVET.objects.all()

    best_answer = None
    best_accuracy = 0

    for ans in answers:
        keywords = [k.strip().lower() for k in ans.keywords.split(',')]
        total_score = 0

        for k_word in keywords:
            best_similarity = 0

            for q_word in question_words:
                sim = word_similarity(q_word, k_word)
                if sim > best_similarity:
                    best_similarity = sim

            total_score += best_similarity

        # делим на количество keywords
        accuracy = (total_score / len(keywords)) * 100 if keywords else 0

        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_answer = ans

    return best_answer, round(best_accuracy, 1)