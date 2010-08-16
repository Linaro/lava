"""
Helper package for working with JSON and custom classes.

This module defines IFundamentalJSONType, ISimpleJSONType and
IComplexJSONType. All those interfaces can be used with the custom
encoder and decoder classes (.encoder.PluggableJSONEncoder and
.decoder.PluggableJSONDecoder respectively) to store arbitrary objects.
Some operations require global type awareness and type registration.
This is performed by ClassRegistry class. A default instance called
DefaultClassRegistry is provided when no special constraints are
required.

Most common use cases are supported by the .pod.PlainOldData class that
simply serializes all public attributes and properties. See
documentation below for more details.

:Tutorial

The simple tutorial below shows how to use all features in a
step-by-step fashion. The tutorial first shows the manual method where
all required methods are written explicitly. Then it shows how the POD
class can help reduce the boilerplate code to bare minimum. Finally it
touches a more advanced topic with static type declarations.

:Tutorial Part One: IComplexJSONType

Note: despite the name IComplexJSONType is actually quite easy to use
and is the recommended way to add JSON support to arbitrary objects. If
you want to know about other interfaces see the advanced topics section
at the end of the document.

First let's define the Person class with one helper method.
>>> class Person(IComplexJSONType):
...     def __init__(self, name):
...         self.name = name
...     def to_json(self):
...         return {'name': self.name}

Let's make a person instance:
>>> joe = Person('Joe')
>>> joe.name
'Joe'

We can now serialize this object using json.dumps() or any other json
module API. The only requirement is to pass our generic pluggable
encoder class:
>>> from .encoder import PluggableJSONEncoder
>>> json.dumps(joe, cls=PluggableJSONEncoder, class_hint=None)
'{"name": "Joe"}'

The function json.dumps accepts arbitrary arguments and passes most of
them to the encoder. The encoder class is selected by the cls argument.
We had to specify one more argument, class_hint. This argument is
specific to PluggableJSONEncoder and dictates how type information is
encoded. Currently we chose not to encode it in any way.

This JSON data is good but not very useful. It lacks any reference to
the Person class. To recreate our object we need to add two more
methods.

>>> class Person(IComplexJSONType):
...     def __init__(self, name):
...         self.name = name
...     @classmethod
...     def get_json_class_name(cls):
...         return 'Person'
...     def to_json(self):
...         return {'name': self.name}
...     @classmethod
...     def from_json(cls, doc):
...         return cls(doc['name'])

Let's recreate Joe instance with the new definition.
>>> joe = Person('Joe')

And see how it the representation will look like now. We also omit
class_hint argument and let the defaults work. By default class name (as
obtained from get_json_class_name() is stored as the "__class__"
attribute. Observe:
>>> joe_json = json.dumps(joe, cls=PluggableJSONEncoder)
>>> joe_json
'{"name": "Joe", "__class__": "Person"}'

That's more like it! It has all the pieces required to load it back into
python! All we have to do is tell our decoder that "Person" string
refers to the Person class. To do that we'll use the default class
registry provided by this module. This call returns the class itself so
that it can be used as a class decorator. We're not using this feature
because it requires python 2.6.
>>> DefaultClassRegistry.register(Person) # doctest: +ELLIPSIS
<class '....Person'>

Now we are ready to recreate Joe. Note that both the type and all
attributes were retained.
>>> from .decoder import PluggableJSONDecoder
>>> joe = json.loads(joe_json, cls=PluggableJSONDecoder)
>>> type(joe) is Person
True

There is _one_ twist though. All JSON strings became Unicode!
>>> joe.name
u'Joe'

This is an inherent property of using JSON (it is defined in terms of
Unicode characters). If you need to work with byte objects you have to
dig deeper into the advanced topics. Since using JSON to store raw bytes
(as in contents of photos and other big files) is not really a good idea
this limitation will not affect most users.

:Tutorial Part 2: PlaindOldData

Since what we did with Person class is pretty common and having to write
all those methods over and over would be tedious we can use the
PlainOldData class to simplify the process. PlainOldData implements
most of IComplexJSONType as well as adds several useful methods not
strictly related to JSON. PlainOldData is in the .pod module.
>>> from .pod import PlainOldData

Let's recreate Person class. Notice how none of the "JSON" part is now a
part of our class!

>>> class Person(PlainOldData):
...     def __init__(self, name):
...         self.name = name

Note: There is an important convention when using PlainOldData.  All
attributes _must_ be available as constructor arguments. This is how the
provided from_json() method works. It just calls the constructor with
all arguments. We've been doing this so far but it is important to
mention this explicitly.

Note: As we keep re-defining the Person class we need to update the
class registry to point to the latest version. Normally you would do
this just once.
>>> DefaultClassRegistry.register(Person) # doctest: +ELLIPSIS
<class '....Person'>

PlainOldData support simple __repr__() pretty printing:
>>> Person('Joe')
<Person name:'Joe'>

JSON Serialization:
>>> json.dumps(Person("Frank"), cls=PluggableJSONEncoder)
'{"name": "Frank", "__class__": "Person"}'

JSON De-serialization:
>>> json.loads('{"name": "Bob", "__class__": "Person"}',
...     cls=PluggableJSONDecoder)
<Person name:u'Bob'>

As well as field-by-field comparison and ordering:
>>> Person("Joe") == Person("Joe")
True

:Tutorial Part 3: Static Type Definitions

Using static type definition allows us to make the JSON documents a
little more "human" by dropping all the __class__ attributes that don't
look very friendly. The basic idea is: instead of deciding how to decode
each object by looking at the JSON document the user (developer)
provides a type expression that describes the root object (in the JSON
document) and each serialized class has a static type structure (for all
attributes) so that we can recursively determine the correct type of
each object.

Let's start with an example. We'll define a PetOwner and Pet classes and
allow people to have pets.

>>> class Pet(PlainOldData):
...     def __init__(self, kind):
...         self.kind = kind

>>> class PetOwner(PlainOldData):
...     def __init__(self, pets=None):
...         self.pets = pets or []
...     @classmethod
...     def get_json_attr_types(cls):
...         return {'pets': [Pet]}


There is a new class method get_json_attr_types(). It allows us to tell
the decoder about static type expectations. The syntax is simple (it
maps attribute names to type expressions) but see the documentation for
description of supported type expressions. Here the type expression says
"it's an array of Pets".

One nice aspect of static type definitions is that we no longer need
type registration.

Let's compose some data and serialize it. As you can see the representation
is very natural. It really does resemble a hand-made data model.
>>> owner = PetOwner([Pet("cat"), Pet("dog")])
>>> json.dumps(owner, cls=PluggableJSONEncoder, class_hint=None)
'{"pets": [{"kind": "cat"}, {"kind": "dog"}]}'

Getting that data back into python requires some more work. Previously
we were calling json.loads() with our custom decoder class. This time
we need to provide one additional argument, the type expression of the
root object. This is just the initial description on how to interpret
the data. The decoder will use that to interrogate each type it
encounters. Let's see how this works.

>>> json.loads('{"pets": [{"kind": "cat"}, {"kind": "dog"}]}',
...     cls=PluggableJSONDecoder, type_expr=PetOwner)
<PetOwner pets:[<Pet kind:u'cat'>, <Pet kind:u'dog'>]>

The most simple type expression is a class. It means that
the root object is a single instance of that class.
>>> json.loads('{"kind": "cat"}', cls=PluggableJSONDecoder,
...     type_expr=Pet)
<Pet kind:u'cat'>

There are just two more type expressions possible. First one is "an
array of items of the specified type". You can express by putting a type
expression in a python list. Here's an example:
>>> json.loads('[{"kind": "cat"}, {"kind": "fish"}]',
...     cls=PluggableJSONDecoder, type_expr=[Pet])
[<Pet kind:u'cat'>, <Pet kind:u'fish'>]

Note that it can nest as much as you like. A list of lists is fine:
>>> json.loads('[[{"kind": "mouse"}]]',
...     cls=PluggableJSONDecoder, type_expr=[[Pet]])
[[<Pet kind:u'mouse'>]]

The final type expression is a dictionary. Here each key to value can
designate different type.
>>> json.loads('{"bad": {"kind": "wolf"}, "good": {"kind": "dog"}}',
...     cls=PluggableJSONDecoder, type_expr={"bad": Pet, "good": Pet})
{u'bad': <Pet kind:u'wolf'>, u'good': <Pet kind:u'dog'>}

:Tutorial Part 4: Using proxy types

The first problem you will likely encounter as you start using this
library is "how do I serialize that 3rd party class" without making each
of my to_json() and from_json() methods in classes that may use them
painfully aware of it? Since it's not your code you cannot implement
IComplexJSONType or inherit from PlainOldData. You have to encode each
value yourself and it begs for some general method of dealing with
foreign types.

The solution is to write a proxy class and register it with the
ClassRegistry instance using register_proxy(). A proxy class will be
instantiated with the original object as sole argument every time you
want to serialize an instance of the proxied class.

Let's see an example:
>>> from datetime import datetime

>>> class datetime_proxy(IComplexJSONType):
...     def __init__(self, obj):
...         self.obj = obj
...     def to_json(self):
...         return {"date": self.obj.strftime("%Y-%m-%d")}
...     @classmethod
...     def get_json_class_name(cls):
...         return "datetime"
...     @classmethod
...     def from_json(cls, json_doc):
...         return datetime.strptime(json_doc["date"], "%Y-%m-%d")

>>> DefaultClassRegistry.register_proxy(datetime, datetime_proxy) # doctest: +ELLIPSIS

We can now serialize any datetime instances!
>>> json.dumps(datetime(2010, 07, 30), cls=PluggableJSONEncoder,
...     sort_keys=True)
'{"__class__": "datetime", "date": "2010-07-30"}'

And load them back. It's my birthday :-)
>>> json.loads('{"date": "2010-08-19", "__class__": "datetime"}',
...     cls=PluggableJSONDecoder)
datetime.datetime(2010, 8, 19, 0, 0)

:Tutorial Part 5: Using ISimpleJSONType

This part of the tutorial starts dealing with advanced topics. You will
most likely not have to deal with those parts very often but knowing
them is useful if you want to make beautiful and natural JSON documents.

This interface has been designed to serialize data that has no native
JSON representation but would not look very good as a
dictionary-with-attributes produced by IComplexJSONType.

A good example would be the datetime.datetime class. Would you really
like to have a {"year": 2010, "month": 7, .......} (it's quite long)
entry instead of a string like "2010-07-12 15:35:21"?

So here's how it works:
    * You have to use static type declarations to use ISimpleJSONType
    * You can store anything you like as a single JSON string
    * You have to parse it back
    * All the methods are the same as before.

Instead of doing a full blown example here I'd like to point you to the
datetime_proxy class defined in the .proxies.datetime module.
"""

# Required since we have json module that is also defined in the
# standard library.
from __future__ import absolute_import

from .impl import json
from .decoder import PluggableJSONDecoder
from .encoder import PluggableJSONEncoder
from .interface import IFundamentalJSONType, ISimpleJSONType, IComplexJSONType
from .registry import ClassRegistry, DefaultClassRegistry
from .pod import PlainOldData
