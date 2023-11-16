from django.conf import settings
import json

class Modal:
    def __init__(self, title, submit_label, blocks=None, state=None):
        self.title = title
        self.submit_label = submit_label
        self.state = state
        self.blocks = blocks

    def add_block(self, block):
        if not self.blocks:
            self.blocks = []
        self.blocks.append(block)

    def set_state(self, state):
        self.state = state

    def build_modal(self, callback_id):
        blocks = []
        for block in self.blocks:
            blocks.append(block.to_block())

        modal = {
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": self.title
            },
            "submit": {
                "type": "plain_text",
                "text": self.submit_label
            },
            "callback_id": callback_id,
            "blocks": blocks
        }

        if self.state:
            modal["private_metadata"] = json.dumps(self.state)
        else:
            modal["private_metadata"] = ''
        
        return modal

    def send_open_modal(self, callback_id, trigger_id):
        """
        Open the modal
        """
        return settings.SLACK_CLIENT.views_open(
            modal=self.build_modal(callback_id), trigger_id=trigger_id
        )


class Element:
    def __init__(self, label, name, optional, hint, value, placeholder):
        self.label = label
        self.name = name
        self.optional = optional
        self.hint = hint
        self.value = value
        self.placeholder = placeholder

    def to_block_base(self):
        return {
            "type": "input",
            "block_id": self.name,
            "element": {
                "type": self.element_type,
                "action_id": self.name
            },
            "label": {
                "type": "plain_text",
                "text": self.label
            },
            "optional": self.optional
        }

    def to_block(self):
        block = self.to_block_base()
        if self.hint:
            block["hint"] = {
                "type": "plain_text",
                "text": self.hint
            }
        if self.placeholder:
            block["element"]["placeholder"] = {
                    "type": "plain_text",
                    "text": self.placeholder
                }
            
        return block    


class Text(Element):
    def __init__(
        self,
        label=None,
        name=None,
        optional=False,
        hint=None,
        value=None,
        placeholder=None,
    ):
        super().__init__(label, name, optional, hint, value, placeholder)
        self.element_type = 'plain_text_input'

    def to_block(self):
        block = super().to_block_base()
        block['element']["initial_value"] = self.value

        return block

class TextArea(Element):
    def __init__(
        self,
        label=None,
        name=None,
        optional=False,
        hint=None,
        value=None,
        placeholder=None,
        multiline=False
    ):
        super().__init__(label, name, optional, hint, value, placeholder)        
        self.element_type = 'plain_text_input'
        self.multiline = multiline

    def to_block(self):
        block = super().to_block_base()     
        block['element']["initial_value"] = self.value   
        block['element']["multiline"] = self.multiline

        return block

class SelectWithOptions(Element):
    def __init__(
        self,
        options,
        label=None,
        name=None,
        optional=False,
        hint=None,
        value=None,
        placeholder=None,
    ):
        super().__init__(label, name, optional, hint, value, placeholder)
        self.element_type = 'static_select'
        self.options = [{"label": lbl, "value": val} for lbl, val in options]

    def to_block(self):
        block = super().to_block_base()
        block['element']['options'] = [
            {
                'text': {'type': 'plain_text', 'text': option['label']},
                'value': option['value']
            } for option in self.options
        ]

        return block

class SelectFromUsers(Element):
    def __init__(
        self,
        label=None,
        name=None,
        optional=False,
        hint=None,
        value=None,
        placeholder=None,
    ):
        super().__init__(label, name, optional, hint, value, placeholder)
        self.element_type = 'users_select'
        