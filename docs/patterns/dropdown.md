
### Dropdown

This is the HTML structure needed to use the existing dropdown javascript functionality.  

- You can add the is-hover class to show/hide the dropdown when the user places their mouse over the button.

```html
<div class="dropdown">
    <div class="dropdown-trigger">
        <button class="button is-info">
            <span>Search</span>
            <span class="icon is-small">
                <i class="fa fa-magnifying-glass" aria-hidden="true"></i>
            </span>
        </button>
    </div>
    <div class="dropdown-menu">
        <div class="dropdown-content">
            <a href="#" class="dropdown-item">
                This is a link
            </a>
        </div>
    </div>
</div>
```
