import feedparser
feed_url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=USDKRW=X&region=US&lang=en-US"
feed = feedparser.parse(feed_url)
for entry in feed.entries[:3]:
    print("Title:", getattr(entry, "title", "N/A"))
    print("Published:", getattr(entry, "published", "N/A"))
