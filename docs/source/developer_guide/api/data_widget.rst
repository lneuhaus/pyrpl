DataWidget
*************

There are many places in pyrpl where we need to plot datasets. A unified
API to deal with the following needs would make the code more
maintainable: - Plotting several channels on the same widget (for
instance with a multidimensional array as input) - Automatic switching
between real and complex datasets (with appearance/disappearance of a
phase plot) - Dealing with different transformations for the magnitude
(linear, dB, dB/Hz...). Since we would like the internal data to stay as
much as possible independent of the unit chosen for their graphical
representation, I would advocate for the possibility to register
different unit/conversion\_functions options (mainly for the magnitude I
guess) at the widget level. - For performance optimization, we need to
have some degree of control over how much of the dataset needs to be
updated. For instance, in the network analyzer, there is currently a
custom signal: update\_point(int). When the signal is emitted with the
index of the point to update, the widget waits some time (typically 50
ms) before actually updating all the required points at once. Moreover,
the curve is updated by small fragments (chunks) to avoid the bottleneck
of redrawing millions of points every 50 ms for very long curves.

If we only care for the 3 first requirements, it is possible to make a
pretty simple API based on the attribute/widget logic (eventhough we
need to define precisely how to store the current unit). For the last
requirement, I guess we really need to manually create a widget (not
inheriting from AttributeWidget, and deal manually with the custom
signal handling).

That's why, I propose a DataWidget (that doesn't inherit from
AttributeWidget) which would expose an API to update the dataset point
by point and a DataAttributeWidget, that would ideally be based on
DataWidget (either inheritance or possession) to simply allow
module.some\_dataset = some\_data\_array.

Another option is to keep the current na\_widget unchanged (since it is
already developed and working nicely even for very large curves), and
develop a simple DataAttributeWidget for all the rest of the program.

The last option is probably much easier to implement quickly, however,
we need to think whether the point-by-point update capability of the
na\_widget was a one-time need or whether it will be needed somewhere
else in the future...
