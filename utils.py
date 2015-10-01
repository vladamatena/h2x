# Part of J2J (http://JRuDevels.org)
# Copyright 2007 JRuDevels.org

from twisted.words.protocols.jabber import jid

def addDiscoItem(query, jid, name=None, node=None):
    item=query.addElement("item")
    item.attributes["jid"]=jid
    if name:
        item.attributes["name"]=name
    if node:
        item.attributes["node"]=node
    return item

def createForm(iq,formType):
    form=iq.addElement("x")
    form.attributes["xmlns"]="jabber:x:data"
    form.attributes["type"]=formType
    return form

def addTitle(form,caption):
    title=form.addElement("title",content=caption)
    return title

def addTextBox(form,name,caption,value,required=False):
    textBox=form.addElement("field")
    textBox.attributes["type"]="text-single"
    textBox.attributes["var"]=name
    textBox.attributes["label"]=caption
    value=textBox.addElement("value",content=value)
    if required:
        textBox.addElement("required")
    return textBox
