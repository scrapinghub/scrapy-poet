from scrapy_po.webpage import callback_for, ItemPage


def test_callback_for():

    class FakePage(ItemPage):

        def to_item(self):
            return 'it works!'

    cb = callback_for(FakePage)
    assert callable(cb)

    fake_page = FakePage()
    assert list(cb(page=fake_page)) == ['it works!']
