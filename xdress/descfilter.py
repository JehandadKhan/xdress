"""Filters parsed code to exclude methods or attributes that have certain
types as input parameters.

This module is available as the xdress plugin ``xdress.descfilter``.

:author: Spencer Lyon <spencerlyon2@gmail.com>

Filtering
=========

This plugin alters the description dictionary generated by other xdress
plugins (mainly ``xdress.autodescribe``) by removing attributes or
methods that contain argument types the user wishes to exclude from the
generated cython wrapper. To use ``xdress.descfilter``, you need to do
two things in the xdressrc file for your project.

1. Add it to the list of plugins
2. Define one or more of the following:

   a. ``skiptpyes``, a  list or dictionary. If ``skiptypes`` is a
      dictionary the keys are class names and the values are lists (or
      tuples) of data types that should be left out of the generated
      code for the class. If ``skiptypes`` is a list or tuple, the
      skipped types will be applied to all classes listed in the
      ``classes`` list in xdressrc. If ``skiptypes`` is empty or
      ``None`` this plugin will not try to filter any types.
   b. ``skipmethods`` dictionary. The keys for this dictionary
      are the class names and the values are a list of method names that
      should be excluded from the wrapper.
   c. ``skipattrs`` dictionary. The keys for this dictionary are
      the class names and the values are a list of class attributes
      that should be excluded from the wrapper.
   d. ``includemethods`` dict. This is the complement of the
      ``skipmethods`` dict. The keys are class names and the values are
      list of methods that should be included in the wrapper. All
      other methods are filtered out.
   e. ``skipauto`` boolean.  If this is ``True`` then methods and attributes
      with any types that are unknown will be filtered out.

.. warning::

    It is important that ``xdress.descfilter`` comes after
    ``xdress.autoall``, and ``xdress.autodescribe`` but before
    ``xdress.cythongen``. This is necessary because the description
    dictionary needs to be populated by autodescribe before descfilter
    can act on it, but it also must do the filtering before cythongen
    generates any code.

Type Filtering Example
======================

To filter specific types you might do something like this in xdressrc::

    # Declare use of plugin (point 1)
    plugins = ('xdress.stlwrap', 'xdress.autoall', 'xdress.autodescribe',
               'xdress.descfilter', 'xdress.cythongen')

    # Specify skiptypes (point 2)
    skiptypes = {'classA': ['float64', (('int32', 'const'), '&')],
                 'classB': ['classA', ('vector', 'float32')]}

I also could have done the following to exclude all instances of
particular types, regardless of the class in which they arise.

    skiptypes = ['uint32', (('vector', 'float64', 'const'), '&')]

A Closer Look
-------------

As of right now ``xdress.descfilter`` is set up to handle skiptype
elements of two flavors.

1. A single type identifier. This could be any base type,  (e.g. int32,
   char, float64, ect), an STL type (e.g. vector, map, set), or any type
   xdress knows about (like classA in the first example above). In this
   case xdress will flatten all argument types and if the single type
   identifier appears anywhere in the flattened argument description,
   the method will be filtered out.

   For example, if 'float64' were in the ``skiptypes`` it would catch any
   of the following argument types (this is by no means a complete list)::

        "float64"
        (('vector', 'float64', 'const'), '&')
        ('set', 'float64')

2. A specific argument or return type that will match exactly. This
   option provides more control over what ``xdress.descfilter`` will
   catch and can prevent the plugin from being to ambitious with regards
   to the methods that are filtered out.

Typically, the first option would be used in situations where xdress,
for whatever reason, cannot create a wrapper for a user-defined C++
class. This might happen due to limitations with xdress itself, or
perhaps limitations with Cython.

Users are advised to use the second option in most other circumstances
in order to forestall any potential issues with needed methods not
being wrapped.

Method Filtering Example
========================

Suppose, in the C++ source, I had a class ``Computer`` with the
following methods:

    checkEmail
    turnOn
    blowUp
    runXdress
    sleep
    crash

Now, if I didn't want python users to have access to the ``blowUp``,
``sleep``, or ``crash`` methods, I would put the following in my
xdressrc file::

    # Declare use of plugin (point 1)
    plugins = ('xdress.stlwrap', 'xdress.autoall', 'xdress.autodescribe',
               'xdress.methodfilter', 'xdress.cythongen')

    # Specify methods to skip (point 2)
    skipmethods = {'Computer': ['blowUp', 'sleep', 'crash']}

Description Filtering API
=========================
"""
from __future__ import print_function
import sys
import collections
from .utils import isclassdesc, NotSpecified
from .type.matching import TypeMatcher
from .plugins import Plugin

if sys.version_info[0] >= 3:
    basestring = str

def modify_desc(skips, desc):
    """Deletes specified methods from a class description (desc).

    Parameters
    ----------
    skips : dict or list
        The attribute rc.skiptypes from the run controller managing
        the desc dictionary. This is filled with
        xdress.typesystem.TypeMatcher objects and should have been
        populated as such by xdress.descfilter.setup

    desc : dictionary
        The class dictionary that is to be altered or tested to see
        if any methods need to be removed.

    """
    # remove attrs with bad types
    for at_name, at_t in desc['attrs'].copy().items():
        for tm in skips:
            if tm.flatmatches(at_t):
                del desc['attrs'][at_name]
                break

    # remove methods with bad parameter types or return types
    for m_key, m_ret in desc['methods'].copy().items():
        _deleted = False
        # Check return types
        for tm in skips:
            if m_ret and tm.flatmatches(m_ret['return']):
                del desc['methods'][m_key]
                _deleted = True
                break

        # Stop here if we already got it
        if _deleted:
            continue

        m_args = m_key[1:]

        for arg in m_args:
            t = arg[1]  # Just use type, not parameter name or default val
            for tm in skips:
                # c1 = tm.flatmatches(t)
                # c2 =
                if tm.flatmatches(t):
                    del desc['methods'][m_key]
                    _deleted = True
                    break

            if _deleted:
                break


class XDressPlugin(Plugin):
    """Plugin for filtering API description dictionaries."""

    # Require base, autoall, and autodescribe so that rc.env is populated
    requires = ('xdress.autodescribe',)

    defaultrc = {'skiptypes': NotSpecified,
                 'skipmethods': NotSpecified,
                 'includemethods': NotSpecified,
                 'skipattrs': NotSpecified,
                 'skipauto': NotSpecified}

    rcdocs = {
        'skiptypes': 'The types to filter out from being wrapped',
        'skipmethods': 'Method names to filter out from being wrapped',
        'skipattrs': 'Method names to filter out from being wrapped',
        'includemethods': 'Method names to be wrapped (dict, keys are class names)',
        'skipauto': 'Try and skip anything that uses an unknown type',
        }

    def setup(self, rc):
        if rc.skiptypes is NotSpecified:
            return
        if isinstance(rc.skiptypes, collections.Mapping):
            # Update dict so everything is a TypeMatcher instance
            _skippers = {}
            for kls in rc.skiptypes.keys():
                _skippers[kls] = [TypeMatcher(t) for t in rc.skiptypes[kls]]
            rc.skiptypes = _skippers
        elif isinstance(rc.skiptypes, collections.Sequence):
            # Update tuple or list to be full of TypeMatchers
            rc.skiptypes = [TypeMatcher(t) for t in rc.skiptypes]
            if rc.verbose:
                print("descfilter: skipping these types: {0}".format(rc.skiptypes))

    def skip_types(self, rc):
        """ Remove unwanted types from type descriptions """
        if rc.skiptypes is NotSpecified:
            return
        print("descfilter: removing unwanted types from desc dictionary")
        if isinstance(rc.skiptypes, collections.Mapping):
            skip_classes = rc.skiptypes.keys()
            for mod_key, mod in rc.env.items():
                for kls_key, desc in mod.items():
                    if isclassdesc(desc):
                        if desc['name']['tarname'] in skip_classes:
                            # Pull out skiptypes
                            skips = rc.skips[desc['name']['tarname']]
                            # let modify_desc remove unwanted methods
                            modify_desc(skips, desc)
        elif isinstance(rc.skiptypes, collections.Sequence):
            for mod_key, mod in rc.env.items():
                for kls_key, desc in mod.items():
                    if isclassdesc(desc):
                        skips = rc.skiptypes
                        modify_desc(skips, desc)

    def skip_methods(self, rc):
        """ Remove unwanted methods from classes """
        if rc.skipmethods is NotSpecified:
            return
        print("descfilter: removing 'skipmethods' from desc dictionary")
        skip_classes = rc.skipmethods.keys()
        for m_key, mod in rc.env.items():
            for k_key, kls_desc in mod.items():
                if isclassdesc(kls_desc):
                    if kls_desc['name']['tarname'] in skip_classes:
                        skippers = rc.skipmethods[k_key]
                        m_nms = rc.env[m_key][k_key]['methods'].keys()
                        for m in skippers:
                            # Find method key
                            try:
                                f = lambda x: x[0].startswith(m) \
                                              if isinstance(x[0], basestring) \
                                              else x[0][0].startswith(m)
                                del_key = filter(f, m_nms)[0]
                            except IndexError:
                                msg = 'descfilter: Could not find method {0} '
                                msg += 'in {1}. Moving on to next method'
                                print(msg.format(m, k_key))
                                continue
                            # Remove that method
                            del rc.env[m_key][k_key]['methods'][del_key]

    def skip_attrs(self, rc):
        """ Remove unwanted attributes from classes """
        if rc.skipattrs is NotSpecified:
            return
        print("descfilter: removing 'skipattrs' from desc dictionary")
        skip_classes = rc.skipattrs.keys()
        for m_key, mod in rc.env.items():
            for k_key, kls_desc in mod.items():
                if isclassdesc(kls_desc):
                    if kls_desc['name']['tarname'] in skip_classes:
                        skippers = rc.skipattrs[k_key]
                        a_nms = rc.env[m_key][k_key]['attrs']
                        for m in skippers:
                            if m in a_nms:
                                del rc.env[m_key][k_key]['attrs'][m]
                            else:
                                msg = 'descfilter: Could not find attr {0} '
                                msg += 'in {1}. Moving on to next attr'
                                print(msg.format(m, k_key))

    def include_methods(self, rc):
        """ Alter a class description to include only a subset of methods """
        if rc.includemethods is NotSpecified:
            return
        print("descfilter: removing all but 'includemethods' from desc")
        inc_classes = rc.includemethods.keys()
        for m_key, mod in rc.env.items():
            for k_key, kls_desc in mod.items():
                if isclassdesc(kls_desc):
                    if kls_desc['name']['tarname'] in inc_classes:
                        keeps = set(rc.includemethods[k_key])
                        m_nms = rc.env[m_key][k_key]['methods'].keys()
                        m_keep = filter(lambda x: x[0] in keeps, m_nms)
                        new_meths = {}
                        for mm in m_keep:
                            new_meths[mm] = rc.env[m_key][k_key]['methods'][mm]
                        rc.env[m_key][k_key]['methods'] = new_meths

    def skip_auto(self, rc):
        """ Automatically remove any methods or attributes that use unknown types """
        if rc.skipauto is NotSpecified:
            return
        ts = rc.ts

        for src_name, cls_dict in rc.env.items():
            for cls_name, cls_desc in cls_dict.items():
                if isclassdesc(cls_desc):

                    attr_blacklist = []
                    for a_name, a_type in cls_desc['attrs'].items():
                        try:
                            ts.canon(a_type)

                        except TypeError:
                            print('descfilter: removing attribute {0} from class {1} '
                                  'since it uses unknown type {2}'.format(
                                    a_name, cls_name, a_type))
                            attr_blacklist.append(a_name)
                    for a in attr_blacklist:
                        del cls_desc['attrs'][a]

                    method_blacklist = []
                    for m_sig, m_attr in cls_desc['methods'].items():
                        m_name = m_sig[0]
                        try:
                            if m_attr is not None:
                                r_type = m_attr['return']
                                arg_type = r_type
                                ts.canon(r_type)
                                pass
                            for _, arg_type in m_sig[1:]:
                                ts.canon(arg_type)
                        except TypeError:
                            print('descfilter: removing method {0} from class {1} '
                                  'since it uses unknown type {2}'.format(
                                    m_name, cls_name, arg_type))
                            method_blacklist.append(m_sig)

                    for m in method_blacklist:
                        del cls_desc['methods'][m]

    def execute(self, rc):
        self.skip_types(rc)
        self.skip_methods(rc)
        self.skip_attrs(rc)
        self.skip_auto(rc)
        self.include_methods(rc)
