selectors = {
    "opinion_id": (None, 'data-entry-id'),
    "author": ("span.user-post__author-name",),
    "recommendation": ("span.user-post__author-recomendation > em",),
    "stars": ("span.user-post__score-count",),
    "content": ("div.user-post__text",),
    "pros": ("div.review-feature__item--positive", None, True),
    "cons": ("div.review-feature__item--negative", None, True),
    "useful": ("button.vote-yes > span",),
    "unuseful": ("button.vote-no > span",),
    "post_date": ("span.user-post__published > time:nth-child(1)",'datetime'),
    "purchase_date": ("span.user-post__published > time:nth-child(2)",'datetime'),
}

def extract_feature(ancestor, selector=None, attribute=None, multiple=False):
    if selector:
        if multiple:
            if attribute:
                return [tag[attribute].strip() for tag in ancestor.select(selector)]
            return [tag.text.strip() for tag in ancestor.select(selector)]     
        if attribute:
            try:
                return ancestor.select_one(selector)[attribute].strip()
            except TypeError:
                return None
        try:
            return ancestor.select_one(selector).text.strip()
        except AttributeError:
            return None
    if attribute:
        return ancestor[attribute].strip()
    return ancestor.text.strip()